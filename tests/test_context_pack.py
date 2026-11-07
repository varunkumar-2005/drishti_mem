"""
tests/test_context_pack.py
Validates the OneContext Repositioning features:
1. Ingest chunks text and retains without duplicates on a re-run
2. A context pack contains a relevant seeded decision
3. A superseded decision is excluded from the context pack
4. The context pack strictly respects max_chars
"""

import time
import uuid
import pytest
from fastapi.testclient import TestClient

from backend.config import get_settings
from backend.core.hindsight_client import HindsightWrapper
from backend.main import app
from backend.storage import local_db


@pytest.fixture
def pack_env(tmp_path, monkeypatch):
    settings = get_settings()
    hindsight = HindsightWrapper(settings)

    test_db = tmp_path / "test_pack.db"
    monkeypatch.setattr(local_db, "DEFAULT_DB_PATH", test_db)
    monkeypatch.setattr(local_db, "get_db_path", lambda custom=None: test_db)
    local_db.init_db(test_db)

    project_id = f"test-pack-{uuid.uuid4().hex[:6]}"
    bank_id = f"onecontext-{project_id}"

    # Provision isolated memory bank in Hindsight Cloud
    hindsight.create_bank(
        bank_id=bank_id,
        name=f"Context Pack Bank ({project_id})",
        mission="Test bank for context pack features",
    )

    local_db.create_project(
        project_id=project_id,
        name="Context Pack Test Project",
        description="Validates context pack generation, ingestion, and capture.",
        bank_id=bank_id,
        db_path=test_db,
    )

    with TestClient(app) as client:
        yield client, project_id, bank_id, hindsight, test_db


def test_ingest_chunks_and_retains_without_duplicates_on_rerun(pack_env):
    """1. Ingest splits long text into chunks and skips duplicates on a re-run."""
    client, project_id, _, _, _ = pack_env

    # Multi-paragraph document with more than 600 words
    paragraph_one = "This is the first architectural section of the service. " * 35
    paragraph_two = "This is the second section detailing database transaction boundaries. " * 35
    paragraph_three = "This is the third section discussing metrics and open telemetry instrumentation. " * 35
    full_doc = f"# Section 1\n\n{paragraph_one}\n\n# Section 2\n\n{paragraph_two}\n\n# Section 3\n\n{paragraph_three}"

    # First ingest
    res1 = client.post(
        f"/projects/{project_id}/ingest",
        json={
            "text": full_doc,
            "source_type": "doc",
            "source_name": "system_design.md",
        },
    )
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["chunks_total"] >= 2
    assert data1["chunks_retained"] >= 2
    assert data1["chunks_skipped"] == 0

    # Second ingest of exact same text (idempotent re-run)
    res2 = client.post(
        f"/projects/{project_id}/ingest",
        json={
            "text": full_doc,
            "source_type": "doc",
            "source_name": "system_design.md",
        },
    )
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["chunks_total"] == data1["chunks_total"]
    assert data2["chunks_retained"] == 0
    assert data2["chunks_skipped"] == data1["chunks_total"]


def test_pack_contains_relevant_seeded_decision(pack_env):
    """2. A context pack contains a relevant seeded decision formatted for the target assistant."""
    client, project_id, bank_id, hindsight, _ = pack_env

    # Capture a distinct architectural decision
    token = f"ProtobufRPC-{uuid.uuid4().hex[:4]}"
    cap_res = client.post(
        f"/projects/{project_id}/capture",
        json={
            "text": f"ADR-77: All inter-service communications under {token} must use gRPC with Protobuf v3 schemas.",
            "source_name": "ADR-77",
        },
    )
    assert cap_res.status_code == 200

    # Wait for Hindsight index
    hindsight.wait_for_recall(bank_id, f"gRPC Protobuf {token}", token, timeout=20)

    # Generate context pack for ChatGPT
    pack_res = client.post(
        f"/projects/{project_id}/context-pack",
        json={
            "task": f"Build client for {token}",
            "target": "chatgpt",
            "max_chars": 3000,
        },
    )
    assert pack_res.status_code == 200
    pack_data = pack_res.json()

    assert "[PROJECT CONTEXT:" in pack_data["pack"]
    assert "[END CONTEXT]" in pack_data["pack"]
    assert token in pack_data["pack"]
    assert f"Build client for {token}" in pack_data["pack"]


def test_superseded_decision_excluded_from_pack(pack_env):
    """3. A superseded decision is excluded from the generated context pack."""
    client, project_id, bank_id, hindsight, _ = pack_env

    token = f"BrokerRule-{uuid.uuid4().hex[:4]}"

    # 1. Retain original decision
    r1 = client.post(
        f"/projects/{project_id}/retain",
        json={
            "text": f"Architecture {token}: Event broker is Apache Kafka cluster with snappy compression.",
            "source": "decision",
            "agent_id": "architect",
        },
    )
    assert r1.status_code == 200
    old_id = r1.json()["memory_id"]

    hindsight.wait_for_recall(bank_id, f"Kafka cluster {token}", token, timeout=20)

    # 2. Correct and supersede it
    r2 = client.post(
        f"/projects/{project_id}/correct",
        json={
            "old_memory_id": old_id,
            "new_text": f"Architecture {token}: Primary event broker is RabbitMQ with AMQP priority queues.",
            "agent_id": "architect",
            "reason": "AMQP protocol requirements",
            "old_memory_text": f"Architecture {token}: Event broker is Apache Kafka cluster with snappy compression.",
        },
    )
    assert r2.status_code == 200

    hindsight.wait_for_recall(bank_id, f"RabbitMQ {token}", "RabbitMQ", timeout=20)

    # 3. Generate context pack
    pack_res = client.post(
        f"/projects/{project_id}/context-pack",
        json={
            "task": f"What is the event broker for {token}?",
            "target": "cursor",
            "max_chars": 3000,
        },
    )
    assert pack_res.status_code == 200
    data = pack_res.json()
    pack_text = data["pack"]
    sources_used_ids = [s.get("id") for s in data["sources_used"]]

    assert "RabbitMQ" in pack_text
    assert old_id not in sources_used_ids
    assert "# Cursor Project Rules:" in pack_text


def test_pack_respects_max_chars(pack_env):
    """4. The generated context pack strictly respects max_chars."""
    client, project_id, bank_id, hindsight, _ = pack_env

    # Capture multiple facts
    token = f"PoolConfig-{uuid.uuid4().hex[:4]}"
    for i in range(3):
        client.post(
            f"/projects/{project_id}/capture",
            json={
                "text": f"PoolRule {i} {token}: Database pool for shard {i} must allocate 25 connections with strict timeouts.",
                "source_name": f"db_rule_{i}",
            },
        )

    hindsight.wait_for_recall(bank_id, f"Database pool {token}", token, timeout=20)

    # Request small max_chars (e.g. 320)
    max_limit = 320
    pack_res = client.post(
        f"/projects/{project_id}/context-pack",
        json={
            "task": f"Configure connection pool for {token}",
            "target": "generic",
            "max_chars": max_limit,
        },
    )
    assert pack_res.status_code == 200
    data = pack_res.json()

    assert data["char_count"] <= max_limit
    assert len(data["pack"]) <= max_limit
