"""
tests/test_phase5_features.py
Unit & integration tests for Phase 5 features:
1. Conflict detection on retain
2. Memory correction and supersession (/correct)
3. Recall and /ask preferring the newest memory
4. Audit trail logging of conflicts and corrections
"""

import uuid
import pytest
from backend.config import get_settings
from backend.core.hindsight_client import HindsightWrapper
from backend.core.llm_client import LLMClient
from backend.core.memory_service import MemoryService
from backend.storage import local_db


@pytest.fixture(scope="module")
def shared_resources():
    settings = get_settings()
    local_db.init_db()
    hindsight = HindsightWrapper(settings)
    llm = LLMClient(settings)
    service = MemoryService(hindsight=hindsight, llm=llm, db_module=local_db)

    project_id = f"test-p5-{uuid.uuid4().hex[:6]}"
    bank_id = f"onecontext-{project_id}"

    hindsight.create_bank(
        bank_id=bank_id,
        name=f"Phase 5 Test Bank ({project_id})",
        mission="Test bank for conflict detection and corrections.",
    )
    local_db.create_project(
        project_id=project_id,
        name="Phase 5 Test Project",
        description="Validates conflict detection and memory corrections.",
        bank_id=bank_id,
    )

    return {
        "service": service,
        "hindsight": hindsight,
        "llm": llm,
        "project_id": project_id,
        "bank_id": bank_id,
    }


def test_conflict_detection_detects_contradiction(shared_resources):
    service = shared_resources["service"]
    hindsight = shared_resources["hindsight"]
    project_id = shared_resources["project_id"]
    bank_id = shared_resources["bank_id"]

    # 1. Retain established policy
    res1 = service.retain(
        project_id=project_id,
        bank_id=bank_id,
        text="DECISION: Public API strictly adheres to REST with OpenAPI 3.1. GraphQL is prohibited.",
        agent_id="agent-planner",
        source="api_design",
        check_conflict=False,
    )
    assert res1["memory_id"]

    # Wait for indexing
    indexed = hindsight.wait_for_recall(bank_id, "REST OpenAPI GraphQL", "REST", timeout=15)
    assert indexed, "Memory should index in Hindsight"

    # 2. Check contradiction with conflicting proposal
    conflicting_text = "PROPOSAL: Migrating public APIs to GraphQL endpoints instead of REST."
    recalled = service.recall(project_id, bank_id, query=conflicting_text, max_results=3)
    conflict = service.conflict_detector.detect_conflict(conflicting_text, recalled)

    assert conflict["has_conflict"] is True, "Should flag contradiction between REST and GraphQL"
    assert conflict["conflicting_memory"] is not None
    assert "REST" in conflict["conflicting_memory"]["text"] or "GraphQL" in conflict["explanation"]


def test_conflict_detection_no_conflict_on_compatible_policy(shared_resources):
    service = shared_resources["service"]
    project_id = shared_resources["project_id"]
    bank_id = shared_resources["bank_id"]

    # Non-conflicting memory (rate limiting)
    neutral_text = "STANDARD: Merchant webhooks timeout after 3.0 seconds."
    recalled = service.recall(project_id, bank_id, query=neutral_text, max_results=3)
    conflict = service.conflict_detector.detect_conflict(neutral_text, recalled)

    assert conflict["has_conflict"] is False, "Independent policy should not flag conflict"


def test_memory_correction_supersedes_old_memory(shared_resources):
    service = shared_resources["service"]
    hindsight = shared_resources["hindsight"]
    project_id = shared_resources["project_id"]
    bank_id = shared_resources["bank_id"]

    # 1. Retain initial decision
    initial = service.retain(
        project_id=project_id,
        bank_id=bank_id,
        text="ARCHITECTURE: Event broker is Apache Kafka.",
        agent_id="infra-lead",
        source="messaging_decision",
        check_conflict=False,
    )
    old_id = initial["memory_id"]
    hindsight.wait_for_recall(bank_id, "Event broker Kafka", "Kafka", timeout=15)

    # 2. Correct and supersede with RabbitMQ
    corr_res = service.correct(
        project_id=project_id,
        bank_id=bank_id,
        old_memory_id=old_id,
        new_text="DECISION (SUPERSEDES KAFKA): RabbitMQ is selected as primary message broker instead of Apache Kafka.",
        agent_id="infra-lead",
        reason="Required AMQP priority queues",
    )

    assert corr_res["status"] == "corrected"
    assert corr_res["supersedes"] == old_id

    # 3. Verify SQLite tracked supersession
    superseded_ids = local_db.get_superseded_memory_ids(project_id)
    assert old_id in superseded_ids

    # 4. Verify recall with include_superseded=False filters out old_id
    recalled_active = service.recall(
        project_id=project_id,
        bank_id=bank_id,
        query="Event broker messaging system",
        max_results=5,
        include_superseded=False,
    )
    active_ids = {m["id"] for m in recalled_active}
    assert old_id not in active_ids


def test_ask_prefers_newest_corrected_memory(shared_resources):
    service = shared_resources["service"]
    project_id = shared_resources["project_id"]
    bank_id = shared_resources["bank_id"]

    # Ask which event broker was chosen
    res = service.ask(
        project_id=project_id,
        bank_id=bank_id,
        question="Which event broker or message broker did we select for the platform?",
    )

    answer = res["answer"].lower()
    # The active decision is RabbitMQ (superseded Kafka)
    assert "rabbitmq" in answer, "Grounded answer must reflect RabbitMQ"
    assert len(res["sources"]) > 0


def test_conflicts_and_corrections_recorded_in_audit_log(shared_resources):
    project_id = shared_resources["project_id"]
    audit = local_db.get_audit(project_id, limit=50)

    actions = [a["action"] for a in audit]
    assert "correct" in actions, "Audit log must track memory correction events"
