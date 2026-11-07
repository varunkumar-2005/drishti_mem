"""
tests/test_live_room.py
Validates the Live Team Room feature:
1. A retained decision creates an event in the room feed
2. Events since a timestamp returns only newer ones
3. A duplicate commit sha does not create a second event (mocked GitHub)
4. A conflict creates a conflict event
5. Catch-up returns 'nothing new' when there are no events
"""

import time
import uuid
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
import httpx

from backend.config import get_settings
from backend.core.hindsight_client import HindsightWrapper
from backend.main import app
from backend.services.github_sync import sync_repo_commits
from backend.storage import local_db


@pytest.fixture
def room_env(tmp_path, monkeypatch):
    settings = get_settings()
    hindsight = HindsightWrapper(settings)

    test_db = tmp_path / "test_room.db"
    monkeypatch.setattr(local_db, "DEFAULT_DB_PATH", test_db)
    monkeypatch.setattr(local_db, "get_db_path", lambda custom=None: test_db)
    local_db.init_db(test_db)

    project_id = f"test-room-{uuid.uuid4().hex[:6]}"
    bank_id = f"onecontext-{project_id}"

    # Provision isolated memory bank in Hindsight Cloud
    hindsight.create_bank(
        bank_id=bank_id,
        name=f"Room Test Bank ({project_id})",
        mission="Test bank for live team room features",
    )

    local_db.create_project(
        project_id=project_id,
        name="Live Room Test Project",
        description="Validates live feed events, presence, and catch-up",
        bank_id=bank_id,
        db_path=test_db,
    )

    # Create team
    team = local_db.create_team(
        name="Alpha Squad",
        project_id=project_id,
        db_path=test_db,
    )

    # Add member
    local_db.add_team_member(
        team_id=team["id"],
        display_name="Alice",
        db_path=test_db,
    )

    with TestClient(app) as client:
        yield client, project_id, team, hindsight, test_db


def test_retained_decision_creates_an_event(room_env):
    """1. A retained decision creates an event in the room events feed."""
    client, project_id, team, _, _ = room_env

    # Retain a decision
    resp = client.post(
        f"/projects/{project_id}/retain",
        json={
            "text": "All API endpoints must return ISO 8601 UTC timestamps.",
            "source": "decision",
            "agent_id": "backend-lead",
        },
    )
    assert resp.status_code == 200

    # Query room events
    events_resp = client.get(f"/rooms/{team['id']}/events")
    assert events_resp.status_code == 200
    events = events_resp.json()

    assert len(events) >= 1
    decision_events = [e for e in events if e["type"] == "decision"]
    assert len(decision_events) >= 1
    assert "ISO 8601" in decision_events[0]["body"]
    assert decision_events[0]["author"] == "backend-lead"


def test_events_since_timestamp_returns_only_newer_ones(room_env):
    """2. Events since a timestamp returns only newer ones."""
    client, project_id, team, _, test_db = room_env

    t1 = "2026-01-01T10:00:00+00:00"
    t2 = "2026-01-01T12:00:00+00:00"
    t3 = "2026-01-01T14:00:00+00:00"

    # Insert events at distinct timestamps
    local_db.record_event(
        project_id=project_id,
        type="decision",
        title="Event 1 (Old)",
        body="First event",
        author="alice",
        created_at=t1,
        db_path=test_db,
    )
    local_db.record_event(
        project_id=project_id,
        type="decision",
        title="Event 2 (Middle)",
        body="Second event",
        author="bob",
        created_at=t2,
        db_path=test_db,
    )
    local_db.record_event(
        project_id=project_id,
        type="decision",
        title="Event 3 (New)",
        body="Third event",
        author="carol",
        created_at=t3,
        db_path=test_db,
    )

    import urllib.parse
    encoded_t1 = urllib.parse.quote(t1)
    resp = client.get(f"/rooms/{team['id']}/events?since={encoded_t1}")
    assert resp.status_code == 200
    events = resp.json()

    titles = [e["title"] for e in events]
    assert "Event 3 (New)" in titles
    assert "Event 2 (Middle)" in titles
    assert "Event 1 (Old)" not in titles


@pytest.mark.asyncio
async def test_duplicate_commit_sha_does_not_create_second_event(room_env):
    """3. A duplicate commit sha does not create a second event (mocked GitHub response)."""
    _, project_id, team, _, test_db = room_env

    mock_commits = [
        {
            "sha": "abc1234567890abcdef1234567890abcdef12345",
            "commit": {
                "message": "feat: add payment idempotency keys",
                "author": {"name": "Dave", "date": "2026-11-07T12:00:00Z"},
            },
        }
    ]

    # Mock httpx AsyncClient
    class MockResponse:
        status_code = 200
        def json(self):
            return mock_commits
        def raise_for_status(self):
            pass

    class MockAsyncClient:
        async def get(self, *args, **kwargs):
            return MockResponse()

    # First sync
    res1 = await sync_repo_commits(
        project_id=project_id,
        repo="mock/repo",
        custom_client=MockAsyncClient(),
    )
    assert res1["synced_count"] == 1

    # Second sync with exact same commit
    res2 = await sync_repo_commits(
        project_id=project_id,
        repo="mock/repo",
        custom_client=MockAsyncClient(),
    )
    assert res2["synced_count"] == 0  # Deduplicated!

    # Verify only 1 commit event exists in SQLite
    events = local_db.get_events(project_id, db_path=test_db)
    commit_events = [e for e in events if e["source_ref"] == "abc1234567890abcdef1234567890abcdef12345"]
    assert len(commit_events) == 1


def test_conflict_creates_conflict_event(room_env):
    """4. Retaining a conflicting decision generates a conflict event."""
    client, project_id, team, _, _ = room_env

    # Retain initial rule
    client.post(
        f"/projects/{project_id}/retain",
        json={
            "text": "The transaction session timeout is strictly set to 5 seconds.",
            "source": "decision",
            "agent_id": "architect",
        },
    )

    # Wait briefly for Hindsight indexing
    time.sleep(2)

    # Retain conflicting rule with check_conflict
    client.post(
        f"/projects/{project_id}/retain",
        json={
            "text": "The transaction session timeout is strictly set to 60 seconds.",
            "source": "decision",
            "agent_id": "contractor",
        },
    )

    # Check room events
    events_resp = client.get(f"/rooms/{team['id']}/events")
    assert events_resp.status_code == 200
    events = events_resp.json()

    conflict_events = [e for e in events if e["type"] == "conflict"]
    assert len(conflict_events) >= 1
    assert "Conflict" in conflict_events[0]["title"]


def test_catch_up_returns_nothing_new_when_there_are_no_events(room_env):
    """5. Catch-up returns 'nothing new' when there are no events."""
    client, _, team, _, test_db = room_env

    # Update member catchup timestamp to the future so there are 0 unseen events
    future_iso = "2099-01-01T00:00:00+00:00"
    local_db.update_member_catchup(team["id"], "Alice", catchup_time=future_iso, db_path=test_db)

    resp = client.post(
        f"/rooms/{team['id']}/catch-up",
        json={"display_name": "Alice"},
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["events_count"] == 0
    assert "Nothing new" in data["summary"]
    assert data["events"] == []
