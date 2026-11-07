"""
tests/test_team_rooms.py
Validates the minimal Team Room feature:
1. create team returns a 6-character alphanumeric code
2. join with a valid code succeeds and lists the member
3. join with an invalid code returns 404
"""

import re
import uuid
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.storage import local_db


@pytest.fixture
def team_env(tmp_path, monkeypatch):
    test_db = tmp_path / "test_teams.db"
    monkeypatch.setattr(local_db, "DEFAULT_DB_PATH", test_db)
    local_db.init_db(test_db)

    project_id = f"proj-{uuid.uuid4().hex[:6]}"
    local_db.create_project(
        project_id=project_id,
        name="Team Test Project",
        description="Testing team rooms",
        bank_id=f"bank-{project_id}",
        db_path=test_db,
    )

    with TestClient(app) as client:
        yield client, project_id, test_db


def test_create_team_returns_six_character_code(team_env):
    """1. create team returns a 6-character code (uppercase letters and digits)."""
    client, project_id, _ = team_env

    resp = client.post("/teams", json={"name": "Frontend Guild", "project_id": project_id})
    assert resp.status_code == 201
    data = resp.json()

    assert data["name"] == "Frontend Guild"
    assert data["project_id"] == project_id
    assert "join_code" in data
    join_code = data["join_code"]
    assert len(join_code) == 6
    assert re.match(r"^[A-Z0-9]{6}$", join_code)


def test_join_with_valid_code_succeeds_and_lists_member(team_env):
    """2. join with a valid code succeeds and lists the member."""
    client, project_id, _ = team_env

    # 1. Create team
    create_resp = client.post("/teams", json={"name": "Backend Guild", "project_id": project_id})
    assert create_resp.status_code == 201
    team = create_resp.json()
    team_id = team["id"]
    join_code = team["join_code"]

    # 2. Join team
    join_resp = client.post("/teams/join", json={"join_code": join_code, "display_name": "Alice"})
    assert join_resp.status_code == 200
    join_data = join_resp.json()

    assert join_data["project_id"] == project_id
    assert join_data["team"]["id"] == team_id
    assert join_data["member"]["display_name"] == "Alice"

    # Join second member
    client.post("/teams/join", json={"join_code": join_code, "display_name": "Bob"})

    # 3. List members
    members_resp = client.get(f"/teams/{team_id}/members")
    assert members_resp.status_code == 200
    members = members_resp.json()

    assert len(members) == 2
    names = [m["display_name"] for m in members]
    assert "Alice" in names
    assert "Bob" in names


def test_join_with_invalid_code_returns_404(team_env):
    """3. join with an invalid code returns 404."""
    client, _, _ = team_env

    resp = client.post("/teams/join", json={"join_code": "INVALID", "display_name": "Charlie"})
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


def test_team_messages_and_collaborator_seed(team_env):
    """4. Seed 4 collaborators and send/list team room chat messages."""
    client, project_id, _ = team_env

    create_resp = client.post("/teams", json={"name": "Auth Squad", "project_id": project_id})
    team_id = create_resp.json()["id"]

    # Seed 4 demo teammates
    seed_resp = client.post(f"/teams/{team_id}/seed-demo")
    assert seed_resp.status_code == 200

    # Verify members
    members_resp = client.get(f"/teams/{team_id}/members")
    assert members_resp.status_code == 200
    members = members_resp.json()
    assert len(members) >= 4
    names = [m["display_name"] for m in members]
    assert "Varun" in names
    assert "Alice" in names

    # Post a message
    msg_resp = client.post(
        f"/teams/{team_id}/messages",
        json={
            "sender": "Alice",
            "role": "security",
            "message": "Updated login logic to 15m RS256 JWT.",
            "message_type": "code_change",
            "retain_as_memory": False,
        },
    )
    assert msg_resp.status_code == 200
    assert msg_resp.json()["sender"] == "Alice"

    # List messages
    msgs_resp = client.get(f"/teams/{team_id}/messages")
    assert msgs_resp.status_code == 200
    msgs = msgs_resp.json()
    assert len(msgs) >= 1
    assert any("RS256" in m["message"] for m in msgs)
