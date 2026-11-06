"""
tests/test_hindsight.py
Integration tests for the HindsightWrapper client.
Uses live Hindsight API against a dedicated test bank: 'onecontext-pytest'.
"""

from __future__ import annotations

import time
import uuid
import pytest
from backend.config import get_settings
from backend.core.hindsight_client import HindsightWrapper

TEST_BANK_ID = "onecontext-pytest"


@pytest.fixture(scope="module")
def hindsight():
    settings = get_settings()
    wrapper = HindsightWrapper(settings)
    # Ensure test bank exists
    wrapper.create_bank(
        bank_id=TEST_BANK_ID,
        name="OneContext PyTest Bank",
        mission="Automated test suite bank for OneContext.",
    )
    yield wrapper
    wrapper.close()


def test_create_bank_idempotent(hindsight: HindsightWrapper):
    """Creating an existing bank should succeed without raising unhandled errors."""
    res1 = hindsight.create_bank(TEST_BANK_ID, "OneContext PyTest Bank")
    res2 = hindsight.create_bank(TEST_BANK_ID, "OneContext PyTest Bank")
    assert res1 is True
    assert res2 is True


def test_retain_and_recall(hindsight: HindsightWrapper):
    """Retaining a unique fact should make it discoverable via wait_for_recall."""
    unique_token = f"postgres-cluster-{uuid.uuid4().hex[:6]}"
    content = f"The production team deployed {unique_token} with read replicas."

    memory_id = hindsight.retain(
        bank_id=TEST_BANK_ID,
        text=content,
        metadata={"source": "test", "agent_id": "pytest-runner"},
    )
    assert memory_id is not None

    # Wait for background indexing using polling helper instead of fixed sleep
    found = hindsight.wait_for_recall(
        bank_id=TEST_BANK_ID,
        query=f"What cluster was deployed? {unique_token}",
        expected_contains=unique_token,
        timeout=25,
        poll_interval=2,
    )
    assert found is True, f"Expected memory containing {unique_token} was not indexed in time"


def test_metadata_roundtrip(hindsight: HindsightWrapper):
    """Metadata passed to retain should be preserved and retrieved during recall."""
    token = f"audit-{uuid.uuid4().hex[:6]}"
    content = f"Security review approved {token} for production deployment."
    custom_project_id = f"proj-{token}"

    hindsight.retain(
        bank_id=TEST_BANK_ID,
        text=content,
        metadata={
            "project_id": custom_project_id,
            "agent_id": "security-bot",
            "source": "compliance",
        },
    )

    # Wait for indexing
    hindsight.wait_for_recall(
        bank_id=TEST_BANK_ID,
        query=f"Security review {token}",
        expected_contains=token,
        timeout=25,
        poll_interval=2,
    )

    results = hindsight.recall(
        bank_id=TEST_BANK_ID,
        query=f"Security review {token}",
        max_results=5,
    )
    assert len(results) > 0

    # Verify at least one result contains our text and has metadata
    matching = [r for r in results if token in r.get("text", "")]
    assert len(matching) > 0, "No recall result contained the token"


def test_recall_query_returns_list(hindsight: HindsightWrapper):
    """Calling recall with a generic query should always return a list."""
    results = hindsight.recall(
        bank_id=TEST_BANK_ID,
        query="database infrastructure",
        max_results=5,
    )
    assert isinstance(results, list)
