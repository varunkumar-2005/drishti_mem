"""
tests/test_memory_service.py
Integration tests for MemoryService orchestration (Hindsight + Groq + SQLite).
"""

from __future__ import annotations

import tempfile
import uuid
import pytest
from pathlib import Path

from backend.config import get_settings
from backend.core.hindsight_client import HindsightWrapper
from backend.core.llm_client import LLMClient
from backend.core.memory_service import MemoryService
from backend.storage import local_db

TEST_BANK_ID = "onecontext-pytest"


@pytest.fixture(scope="module")
def memory_service():
    settings = get_settings()
    hindsight = HindsightWrapper(settings)
    hindsight.create_bank(
        bank_id=TEST_BANK_ID,
        name="OneContext PyTest Bank",
        mission="Automated test suite bank.",
    )
    llm = LLMClient(settings)

    # Temporary test database
    temp_dir = tempfile.mkdtemp()
    test_db_path = Path(temp_dir) / "test_onecontext.db"
    local_db.init_db(db_path=test_db_path)

    # Monkeypatch get_db_path for the test run
    original_get_db_path = local_db.get_db_path
    local_db.get_db_path = lambda custom=None: test_db_path

    service = MemoryService(hindsight=hindsight, llm=llm, db_module=local_db)
    yield service

    local_db.get_db_path = original_get_db_path
    hindsight.close()


def test_retain_logs_audit(memory_service: MemoryService):
    """Retaining a memory must insert a record into the audit log."""
    project_id = f"test-p-{uuid.uuid4().hex[:6]}"
    res = memory_service.retain(
        project_id=project_id,
        bank_id=TEST_BANK_ID,
        text="We selected RabbitMQ for async event dispatching.",
        agent_id="architect-agent",
        source="architecture_decision",
    )

    assert res["project_id"] == project_id
    assert res["agent_id"] == "architect-agent"

    # Check SQLite audit log
    audit_entries = local_db.get_audit(project_id=project_id)
    assert len(audit_entries) >= 1
    assert audit_entries[0]["action"] == "retain"
    assert audit_entries[0]["agent_id"] == "architect-agent"


def test_recall_returns_attributed_results(memory_service: MemoryService):
    """Recalled items must carry attribution fields (agent_id, source)."""
    project_id = f"test-p-{uuid.uuid4().hex[:6]}"
    unique_key = f"key-{uuid.uuid4().hex[:6]}"

    memory_service.retain(
        project_id=project_id,
        bank_id=TEST_BANK_ID,
        text=f"Cache invalidation policy {unique_key} uses TTL of 300 seconds.",
        agent_id="infra-agent",
        source="spec",
    )

    # Wait for indexing
    memory_service.hindsight.wait_for_recall(
        bank_id=TEST_BANK_ID,
        query=f"Cache TTL {unique_key}",
        expected_contains=unique_key,
        timeout=25,
        poll_interval=2,
    )

    results = memory_service.recall(
        project_id=project_id,
        bank_id=TEST_BANK_ID,
        query=f"Cache TTL {unique_key}",
        max_results=5,
    )

    assert isinstance(results, list)
    assert len(results) > 0
    # Every returned item has the expected schema shape
    for r in results:
        assert "text" in r
        assert "id" in r


def test_ask_returns_answer_with_sources(memory_service: MemoryService):
    """Grounded ask endpoint must retrieve sources and produce a non-empty answer."""
    project_id = f"test-p-{uuid.uuid4().hex[:6]}"
    unique_framework = f"FrameworkX-{uuid.uuid4().hex[:4]}"

    memory_service.retain(
        project_id=project_id,
        bank_id=TEST_BANK_ID,
        text=f"The backend services are strictly standardized on {unique_framework}.",
        agent_id="lead-agent",
        source="decision",
    )

    # Wait for indexing
    memory_service.hindsight.wait_for_recall(
        bank_id=TEST_BANK_ID,
        query=f"standardized backend {unique_framework}",
        expected_contains=unique_framework,
        timeout=25,
        poll_interval=2,
    )

    response = memory_service.ask(
        project_id=project_id,
        bank_id=TEST_BANK_ID,
        question=f"Which framework are backend services standardized on? ({unique_framework})",
        agent_id="developer-agent",
    )

    assert response["question"] is not None
    assert len(response["answer"]) > 0
    assert response["model_used"] is not None
    assert isinstance(response["sources"], list)


def test_ask_without_memory_has_no_sources(memory_service: MemoryService):
    """Unassisted answering should have an empty sources list."""
    response = memory_service.ask_without_memory(
        question="What is the time complexity of binary search?",
        agent_id="test-agent",
    )

    assert len(response["answer"]) > 0
    assert response["sources"] == []
    assert response["project_id"] is None
    assert response["model_used"] is not None


def test_project_isolation(memory_service: MemoryService):
    """
    Project memory isolation test:
    Data retained in Project A's bank must NEVER be accessible from Project B's bank.
    """
    bank_a = f"onecontext-iso-a-{uuid.uuid4().hex[:4]}"
    bank_b = f"onecontext-iso-b-{uuid.uuid4().hex[:4]}"

    # Provision both isolated banks
    memory_service.hindsight.create_bank(bank_a, "Bank Alpha")
    memory_service.hindsight.create_bank(bank_b, "Bank Beta")

    secret_key = f"ALPHA-SECRET-{uuid.uuid4().hex[:6]}"
    memory_service.retain(
        project_id="proj-a",
        bank_id=bank_a,
        text=f"Confidential Project Alpha token is {secret_key}.",
        agent_id="agent-alpha",
        source="credentials",
    )

    # Confirm Bank A indexes the secret
    indexed = memory_service.hindsight.wait_for_recall(
        bank_id=bank_a,
        query=f"Project Alpha token {secret_key}",
        expected_contains=secret_key,
        timeout=25,
        poll_interval=2,
    )
    assert indexed is True, "Project A memory failed to index"

    # Query Project B with the same query
    results_b = memory_service.recall(
        project_id="proj-b",
        bank_id=bank_b,
        query=f"Project Alpha token {secret_key}",
        max_results=5,
    )

    # Project B must NOT receive Project A's secret
    leaked = [r for r in results_b if secret_key in r.get("text", "")]
    assert len(leaked) == 0, f"Isolation failure! Bank B retrieved Bank A's secret: {leaked}"

