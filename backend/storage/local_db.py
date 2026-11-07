"""
backend/storage/local_db.py
SQLite persistence layer for projects, agents, and audit logs.
Real long-term memory stays in Hindsight.
"""

from __future__ import annotations

import sqlite3
import secrets
import string
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_DB_PATH = Path(__file__).parent.parent.parent / "onecontext.db"


def get_db_path(custom_path: Optional[str | Path] = None) -> Path:
    if custom_path:
        return Path(custom_path)
    return DEFAULT_DB_PATH


def get_connection(db_path: Optional[str | Path] = None) -> sqlite3.Connection:
    path = get_db_path(db_path)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Optional[str | Path] = None) -> None:
    """Initialize SQLite tables if they do not exist."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                bank_id TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS agents (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                name TEXT NOT NULL,
                role TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (project_id) REFERENCES projects(id)
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_log (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                agent_id TEXT NOT NULL,
                action TEXT NOT NULL,
                query_or_text TEXT,
                result_count INTEGER DEFAULT 0,
                timestamp TEXT NOT NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS corrections (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                old_memory_id TEXT NOT NULL,
                old_memory_text TEXT,
                new_memory_id TEXT NOT NULL,
                reason TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS teams (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                join_code TEXT UNIQUE NOT NULL,
                project_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (project_id) REFERENCES projects(id)
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS team_members (
                team_id TEXT NOT NULL,
                display_name TEXT NOT NULL,
                joined_at TEXT NOT NULL,
                FOREIGN KEY (team_id) REFERENCES teams(id)
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS team_messages (
                id TEXT PRIMARY KEY,
                team_id TEXT NOT NULL,
                sender TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'developer',
                message TEXT NOT NULL,
                message_type TEXT NOT NULL DEFAULT 'chat',
                timestamp TEXT NOT NULL,
                FOREIGN KEY (team_id) REFERENCES teams(id)
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS ingested_chunks (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                source_name TEXT NOT NULL,
                source_type TEXT NOT NULL,
                chunk_text TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(project_id, content_hash),
                FOREIGN KEY (project_id) REFERENCES projects(id)
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                type TEXT NOT NULL,
                title TEXT NOT NULL,
                body TEXT,
                author TEXT NOT NULL,
                source_ref TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (project_id) REFERENCES projects(id)
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS project_github (
                project_id TEXT PRIMARY KEY,
                repo TEXT NOT NULL,
                last_sync TEXT,
                last_status TEXT,
                FOREIGN KEY (project_id) REFERENCES projects(id)
            )
            """
        )
        try:
            cursor.execute("ALTER TABLE corrections ADD COLUMN old_memory_text TEXT")
        except Exception:
            pass
        try:
            cursor.execute("ALTER TABLE team_members ADD COLUMN last_seen TEXT")
        except Exception:
            pass
        try:
            cursor.execute("ALTER TABLE team_members ADD COLUMN last_seen_catchup TEXT")
        except Exception:
            pass
        conn.commit()


def create_project(
    project_id: str,
    name: str,
    description: str,
    bank_id: str,
    created_at: Optional[str] = None,
    db_path: Optional[str | Path] = None,
) -> Dict[str, Any]:
    if not created_at:
        created_at = datetime.now(timezone.utc).isoformat()
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO projects (id, name, description, bank_id, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (project_id, name, description, bank_id, created_at),
        )
        conn.commit()
    return {
        "id": project_id,
        "name": name,
        "description": description,
        "bank_id": bank_id,
        "created_at": created_at,
    }


def get_project(project_id: str, db_path: Optional[str | Path] = None) -> Optional[Dict[str, Any]]:
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return dict(row)


def list_projects(db_path: Optional[str | Path] = None) -> List[Dict[str, Any]]:
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM projects ORDER BY created_at DESC")
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def register_agent(
    agent_id: str,
    project_id: str,
    name: str,
    role: str = "",
    created_at: Optional[str] = None,
    db_path: Optional[str | Path] = None,
) -> Dict[str, Any]:
    if not created_at:
        created_at = datetime.now(timezone.utc).isoformat()
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO agents (id, project_id, name, role, created_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET name = excluded.name, role = excluded.role
            """,
            (agent_id, project_id, name, role, created_at),
        )
        conn.commit()
    return {
        "id": agent_id,
        "project_id": project_id,
        "name": name,
        "role": role,
        "created_at": created_at,
    }


def get_agent(
    agent_id: str,
    project_id: str,
    db_path: Optional[str | Path] = None,
) -> Optional[Dict[str, Any]]:
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM agents WHERE id = ? AND project_id = ?",
            (agent_id, project_id),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return dict(row)


def list_agents(
    project_id: str,
    db_path: Optional[str | Path] = None,
) -> List[Dict[str, Any]]:
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM agents WHERE project_id = ? ORDER BY created_at ASC",
            (project_id,),
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def log_audit(
    project_id: str,
    agent_id: str,
    action: str,
    query_or_text: str,
    result_count: int = 0,
    timestamp: Optional[str] = None,
    db_path: Optional[str | Path] = None,
) -> Dict[str, Any]:
    audit_id = str(uuid.uuid4())[:8]
    if not timestamp:
        timestamp = datetime.now(timezone.utc).isoformat()
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO audit_log (id, project_id, agent_id, action, query_or_text, result_count, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (audit_id, project_id, agent_id, action, query_or_text, result_count, timestamp),
        )
        conn.commit()
    return {
        "id": audit_id,
        "project_id": project_id,
        "agent_id": agent_id,
        "action": action,
        "query_or_text": query_or_text,
        "result_count": result_count,
        "timestamp": timestamp,
    }


def get_audit(
    project_id: str,
    limit: int = 50,
    db_path: Optional[str | Path] = None,
) -> List[Dict[str, Any]]:
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM audit_log
            WHERE project_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (project_id, limit),
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def record_correction(
    project_id: str,
    old_memory_id: str,
    new_memory_id: str,
    reason: str = "",
    old_memory_text: str = "",
    created_at: Optional[str] = None,
    db_path: Optional[str | Path] = None,
) -> Dict[str, Any]:
    """Record a memory supersession relationship in SQLite."""
    corr_id = str(uuid.uuid4())[:8]
    if not created_at:
        created_at = datetime.now(timezone.utc).isoformat()
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO corrections (id, project_id, old_memory_id, old_memory_text, new_memory_id, reason, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (corr_id, project_id, old_memory_id, old_memory_text, new_memory_id, reason, created_at),
        )
        conn.commit()
    return {
        "id": corr_id,
        "project_id": project_id,
        "old_memory_id": old_memory_id,
        "old_memory_text": old_memory_text,
        "new_memory_id": new_memory_id,
        "reason": reason,
        "created_at": created_at,
    }


def get_superseded_memory_ids(
    project_id: str,
    db_path: Optional[str | Path] = None,
) -> set[str]:
    """Return all memory IDs in a project that have been superseded by a newer memory."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT old_memory_id FROM corrections WHERE project_id = ?",
            (project_id,),
        )
        rows = cursor.fetchall()
        return {row["old_memory_id"] for row in rows}


def get_superseded_info(
    project_id: str,
    db_path: Optional[str | Path] = None,
) -> Dict[str, Any]:
    """Return both superseded IDs and superseded source texts for semantic exclusion."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT old_memory_id, old_memory_text FROM corrections WHERE project_id = ?",
            (project_id,),
        )
        rows = cursor.fetchall()
        ids = {row["old_memory_id"] for row in rows if row["old_memory_id"]}
        texts = [row["old_memory_text"].strip() for row in rows if row["old_memory_text"]]
        return {"ids": ids, "texts": texts}


def get_corrections(
    project_id: str,
    db_path: Optional[str | Path] = None,
) -> List[Dict[str, Any]]:
    """Return all correction records for a project."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM corrections WHERE project_id = ? ORDER BY created_at DESC",
            (project_id,),
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def generate_join_code(length: int = 6) -> str:
    """Generate a unique 6-character alphanumeric uppercase join code."""
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def create_team(
    name: str,
    project_id: str,
    db_path: Optional[str | Path] = None,
) -> Dict[str, Any]:
    """Create a new team room with a unique 6-character join code."""
    team_id = str(uuid.uuid4())[:8]
    created_at = datetime.now(timezone.utc).isoformat()
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        for _ in range(10):
            join_code = generate_join_code(6)
            cursor.execute("SELECT id FROM teams WHERE join_code = ?", (join_code,))
            if not cursor.fetchone():
                break
        else:
            raise RuntimeError("Could not generate a unique join code")

        cursor.execute(
            """
            INSERT INTO teams (id, name, join_code, project_id, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (team_id, name.strip(), join_code, project_id, created_at),
        )
        conn.commit()
    return {
        "id": team_id,
        "name": name.strip(),
        "join_code": join_code,
        "project_id": project_id,
        "created_at": created_at,
    }


def get_team_by_code(
    join_code: str,
    db_path: Optional[str | Path] = None,
) -> Optional[Dict[str, Any]]:
    """Retrieve team by its 6-character join code."""
    code = join_code.strip().upper()
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM teams WHERE UPPER(join_code) = ?",
            (code,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return dict(row)


def get_team_by_id(
    team_id: str,
    db_path: Optional[str | Path] = None,
) -> Optional[Dict[str, Any]]:
    """Retrieve team by ID."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM teams WHERE id = ?",
            (team_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return dict(row)


def add_team_member(
    team_id: str,
    display_name: str,
    db_path: Optional[str | Path] = None,
) -> Dict[str, Any]:
    """Add a member to a team room."""
    joined_at = datetime.now(timezone.utc).isoformat()
    name = display_name.strip()
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO team_members (team_id, display_name, joined_at)
            VALUES (?, ?, ?)
            """,
            (team_id, name, joined_at),
        )
        conn.commit()
    return {
        "team_id": team_id,
        "display_name": name,
        "joined_at": joined_at,
    }


def list_team_members(
    team_id: str,
    db_path: Optional[str | Path] = None,
) -> List[Dict[str, Any]]:
    """List all members who joined a team room."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT team_id, display_name, joined_at FROM team_members WHERE team_id = ? ORDER BY joined_at ASC",
            (team_id,),
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def add_team_message(
    team_id: str,
    sender: str,
    message: str,
    role: str = "developer",
    message_type: str = "chat",
    db_path: Optional[str | Path] = None,
) -> Dict[str, Any]:
    """Store a team chat or decision message."""
    msg_id = str(uuid.uuid4())[:8]
    ts = datetime.now(timezone.utc).isoformat()
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO team_messages (id, team_id, sender, role, message, message_type, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (msg_id, team_id, sender.strip(), role.strip(), message.strip(), message_type.strip(), ts),
        )
        conn.commit()
    return {
        "id": msg_id,
        "team_id": team_id,
        "sender": sender.strip(),
        "role": role.strip(),
        "message": message.strip(),
        "message_type": message_type.strip(),
        "timestamp": ts,
    }


def list_team_messages(
    team_id: str,
    limit: int = 100,
    db_path: Optional[str | Path] = None,
) -> List[Dict[str, Any]]:
    """List latest messages in a team room."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM team_messages
            WHERE team_id = ?
            ORDER BY timestamp ASC
            LIMIT ?
            """,
            (team_id, limit),
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def is_chunk_ingested(
    project_id: str,
    content_hash: str,
    db_path: Optional[str | Path] = None,
) -> bool:
    """Check if a chunk hash already exists for this project."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id FROM ingested_chunks WHERE project_id = ? AND content_hash = ?",
            (project_id, content_hash),
        )
        return cursor.fetchone() is not None


def record_ingested_chunk(
    project_id: str,
    content_hash: str,
    source_name: str,
    source_type: str,
    chunk_text: str,
    db_path: Optional[str | Path] = None,
) -> bool:
    """Record an ingested chunk hash. Returns True if inserted, False if already exists."""
    chunk_id = str(uuid.uuid4())[:8]
    created_at = datetime.now(timezone.utc).isoformat()
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO ingested_chunks (id, project_id, content_hash, source_name, source_type, chunk_text, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (chunk_id, project_id, content_hash, source_name, source_type, chunk_text, created_at),
            )
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False


def list_ingested_chunks(
    project_id: str,
    db_path: Optional[str | Path] = None,
) -> List[Dict[str, Any]]:
    """List all ingested chunks for a project."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM ingested_chunks WHERE project_id = ? ORDER BY created_at ASC",
            (project_id,),
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


# --- Events Feed & Live Context ---

def record_event(
    project_id: str,
    type: str,
    title: str,
    body: Optional[str] = None,
    author: str = "system",
    source_ref: Optional[str] = None,
    created_at: Optional[str] = None,
    db_path: Optional[str | Path] = None,
) -> Optional[Dict[str, Any]]:
    """
    Record an event for a project's live room feed.
    Deduplicates by (project_id, source_ref) when source_ref is non-empty.
    Returns the event dict if created, or None if skipped as duplicate.
    """
    if not created_at:
        created_at = datetime.now(timezone.utc).isoformat()
    event_id = str(uuid.uuid4())[:12]

    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        if source_ref:
            cursor.execute(
                "SELECT id FROM events WHERE project_id = ? AND source_ref = ?",
                (project_id, source_ref),
            )
            if cursor.fetchone():
                return None  # duplicate

        cursor.execute(
            """
            INSERT INTO events (id, project_id, type, title, body, author, source_ref, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (event_id, project_id, type, title, body or "", author, source_ref, created_at),
        )
        conn.commit()

    return {
        "id": event_id,
        "project_id": project_id,
        "type": type,
        "title": title,
        "body": body or "",
        "author": author,
        "source_ref": source_ref,
        "created_at": created_at,
    }


def get_events(
    project_id: str,
    since: Optional[str] = None,
    limit: int = 50,
    db_path: Optional[str | Path] = None,
) -> List[Dict[str, Any]]:
    """Get live room events newest first, optionally filtered by since timestamp."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        if since:
            cursor.execute(
                """
                SELECT * FROM events
                WHERE project_id = ? AND created_at > ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (project_id, since, limit),
            )
        else:
            cursor.execute(
                """
                SELECT * FROM events
                WHERE project_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (project_id, limit),
            )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


# --- Presence & Heartbeats ---

def update_member_heartbeat(
    team_id: str,
    display_name: str,
    db_path: Optional[str | Path] = None,
) -> Dict[str, Any]:
    """Update member's last_seen heartbeat. If not in team_members, inserts member."""
    now_iso = datetime.now(timezone.utc).isoformat()
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM team_members WHERE team_id = ? AND display_name = ?",
            (team_id, display_name),
        )
        row = cursor.fetchone()
        if row:
            cursor.execute(
                "UPDATE team_members SET last_seen = ? WHERE team_id = ? AND display_name = ?",
                (now_iso, team_id, display_name),
            )
        else:
            cursor.execute(
                """
                INSERT INTO team_members (team_id, display_name, joined_at, last_seen)
                VALUES (?, ?, ?, ?)
                """,
                (team_id, display_name, now_iso, now_iso),
            )
        conn.commit()
    return {"team_id": team_id, "display_name": display_name, "last_seen": now_iso}


def update_member_catchup(
    team_id: str,
    display_name: str,
    catchup_time: Optional[str] = None,
    db_path: Optional[str | Path] = None,
) -> None:
    """Update member's last_seen_catchup timestamp."""
    if not catchup_time:
        catchup_time = datetime.now(timezone.utc).isoformat()
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE team_members SET last_seen_catchup = ? WHERE team_id = ? AND display_name = ?",
            (catchup_time, team_id, display_name),
        )
        conn.commit()


def get_team_member(
    team_id: str,
    display_name: str,
    db_path: Optional[str | Path] = None,
) -> Optional[Dict[str, Any]]:
    """Get a single team member with presence timestamps."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM team_members WHERE team_id = ? AND display_name = ?",
            (team_id, display_name),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return dict(row)


def list_room_members(
    team_id: str,
    db_path: Optional[str | Path] = None,
) -> List[Dict[str, Any]]:
    """List members of a team room with calculated online status (seen within 60s)."""
    now = datetime.now(timezone.utc)
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM team_members WHERE team_id = ? ORDER BY joined_at ASC", (team_id,))
        rows = cursor.fetchall()
        result = []
        for row in rows:
            m = dict(row)
            last_seen_str = m.get("last_seen")
            online = False
            if last_seen_str:
                try:
                    dt = datetime.fromisoformat(last_seen_str.replace("Z", "+00:00"))
                    online = (now - dt).total_seconds() <= 60
                except Exception:
                    online = False
            m["online"] = online
            result.append(m)
        return result


# --- GitHub Sync Storage ---

def save_project_github(
    project_id: str,
    repo: str,
    db_path: Optional[str | Path] = None,
) -> Dict[str, Any]:
    """Configure GitHub repo for project."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO project_github (project_id, repo, last_status)
            VALUES (?, ?, 'configured')
            ON CONFLICT(project_id) DO UPDATE SET repo = excluded.repo, last_status = 'configured'
            """,
            (project_id, repo),
        )
        conn.commit()
    return {"project_id": project_id, "repo": repo, "last_status": "configured"}


def get_project_github(
    project_id: str,
    db_path: Optional[str | Path] = None,
) -> Optional[Dict[str, Any]]:
    """Get GitHub configuration and sync status for project."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM project_github WHERE project_id = ?", (project_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return dict(row)


def update_project_github_sync(
    project_id: str,
    last_sync: str,
    last_status: str,
    db_path: Optional[str | Path] = None,
) -> None:
    """Update sync timestamp and status for project."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE project_github SET last_sync = ?, last_status = ? WHERE project_id = ?",
            (last_sync, last_status, project_id),
        )
        conn.commit()


def list_all_github_projects(
    db_path: Optional[str | Path] = None,
) -> List[Dict[str, Any]]:
    """List all projects that have GitHub repository sync configured."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM project_github")
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
