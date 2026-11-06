"""
tests/test_agents.py
Tests for multi-agent shared memory collaboration and API endpoints.
"""

from __future__ import annotations

import tempfile
import uuid
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from backend.agents.agent_one import PlannerAgent
from backend.agents.agent_two import BuilderAgent
from backend.agents.validator_agent import ValidatorAgent
from backend.config import get_settings
from backend.core.hindsight_client import HindsightWrapper
from backend.core.llm_client import LLMClient
from backend.core.memory_service import MemoryService
from backend.main import app
from backend.storage import local_db

TEST_BANK_ID = "onecontext-pytest-agents"


@pytest.fixture(scope="module")
def agent_system():
    settings = get_settings()
    hindsight = HindsightWrapper(settings)
    hindsight.create_bank(
        bank_id=TEST_BANK_ID,
        name="OneContext PyTest Agents Bank",
    )
    llm = LLMClient(settings)

    # Isolated test database
    temp_dir = tempfile.mkdtemp()
    test_db_path = Path(temp_dir) / "test_agents.db"
    local_db.init_db(db_path=test_db_path)

    orig_get_db_path = local_db.get_db_path
    local_db.get_db_path = lambda custom=None: test_db_path

    memory_service = MemoryService(hindsight=hindsight, llm=llm, db_module=local_db)
    yield {
        "service": memory_service,
        "bank_id": TEST_BANK_ID,
        "hindsight": hindsight,
    }

    local_db.get_db_path = orig_get_db_path
    hindsight.close()


def test_planner_retains_with_own_agent_id(agent_system):
    """Planner agent must retain decisions stamped with its own agent_id."""
    service = agent_system["service"]
    bank_id = agent_system["bank_id"]
    project_id = f"proj-{uuid.uuid4().hex[:6]}"

    planner = PlannerAgent(
        project_id=project_id,
        bank_id=bank_id,
        memory_service=service,
    )

    token = f"auth-rule-{uuid.uuid4().hex[:4]}"
    res = planner.retain(
        text=f"Authentication tokens strictly use HMAC-SHA256 signing with key {token}.",
        source="security_decision",
    )

    assert res["agent_id"] == "agent-planner"
    assert res["project_id"] == project_id

    # Verify audit log reflects agent-planner
    audit = local_db.get_audit(project_id=project_id)
    assert any(a["agent_id"] == "agent-planner" for a in audit)


def test_builder_recalls_planner_decision_without_handoff(agent_system):
    """Builder agent discovers Planner's decision strictly via Hindsight recall."""
    service = agent_system["service"]
    bank_id = agent_system["bank_id"]
    hindsight = agent_system["hindsight"]
    project_id = f"proj-{uuid.uuid4().hex[:6]}"

    planner = PlannerAgent(
        project_id=project_id,
        bank_id=bank_id,
        memory_service=service,
    )

    unique_arch = f"RedisCluster-{uuid.uuid4().hex[:4]}"
    planner.retain(
        text=f"All background cache invalidation is handled by {unique_arch}.",
        source="architecture_decision",
    )

    # Wait for indexing
    hindsight.wait_for_recall(
        bank_id=bank_id,
        query=f"cache invalidation {unique_arch}",
        expected_contains=unique_arch,
        timeout=25,
        poll_interval=2,
    )

    builder = BuilderAgent(
        project_id=project_id,
        bank_id=bank_id,
        memory_service=service,
    )

    # Builder queries memory without knowing Agent 1
    recalled = builder.recall(query=f"cache invalidation {unique_arch}")
    assert len(recalled) > 0
    found_text = " ".join([r.get("text", "") for r in recalled])
    assert unique_arch in found_text


def test_validator_detects_contradiction(agent_system):
    """Validator agent must flag drafts that contradict recalled memories."""
    service = agent_system["service"]
    bank_id = agent_system["bank_id"]
    hindsight = agent_system["hindsight"]
    project_id = f"proj-{uuid.uuid4().hex[:6]}"

    token = f"RuleNoSQL-{uuid.uuid4().hex[:4]}"
    service.retain(
        project_id=project_id,
        bank_id=bank_id,
        text=f"Standard policy {token}: MongoDB and NoSQL databases are strictly forbidden. Only PostgreSQL is permitted.",
        agent_id="agent-planner",
        source="architecture_decision",
    )

    hindsight.wait_for_recall(
        bank_id=bank_id,
        query=f"NoSQL MongoDB forbidden {token}",
        expected_contains=token,
        timeout=25,
        poll_interval=2,
    )

    validator = ValidatorAgent(
        project_id=project_id,
        bank_id=bank_id,
        memory_service=service,
    )

    # Flawed draft proposing MongoDB
    flawed_draft = f"Proposal under {token}: We will store customer records in a MongoDB replica set."
    val_res = validator.validate(draft_text=flawed_draft, check_topic=f"database {token}")

    assert val_res["valid"] is False
    assert len(val_res["contradictions"]) > 0


def test_agent_api_endpoints():
    """Verify FastAPI routes: register, list, run agent, and validate."""
    with TestClient(app) as client:
        # Create project
        p_res = client.post("/projects", json={"name": "Agent Test Project"})
        assert p_res.status_code == 201
        project_id = p_res.json()["id"]

        # Register agents
        reg_res = client.post(
            f"/projects/{project_id}/agents",
            json={"id": "planner-custom", "name": "Planner One", "role": "Planner"},
        )
        assert reg_res.status_code == 201
        assert reg_res.json()["id"] == "planner-custom"

        # List agents
        list_res = client.get(f"/projects/{project_id}/agents")
        assert list_res.status_code == 200
        assert len(list_res.json()) >= 1

        # Run agent
        run_res = client.post(
            f"/projects/{project_id}/agents/planner-custom/run",
            json={"task": "Standardize database connection pool size."},
        )
        assert run_res.status_code == 200
        assert "output" in run_res.json()

        # Validate endpoint
        val_res = client.post(
            f"/projects/{project_id}/validate",
            json={"draft": "Draft proposing standard pool size of 20 connections."},
        )
        assert val_res.status_code == 200
        assert "valid" in val_res.json()
