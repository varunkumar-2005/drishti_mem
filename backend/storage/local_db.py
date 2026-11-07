"""
backend/storage/local_db.py
SQLite persistence layer for projects, agents, and audit logs.
Real long-term memory stays in Hindsight.
"""

from __future__ import annotations

import sqlite3
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
                new_memory_id TEXT NOT NULL,
                reason TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
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
            INSERT INTO corrections (id, project_id, old_memory_id, new_memory_id, reason, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (corr_id, project_id, old_memory_id, new_memory_id, reason, created_at),
        )
        conn.commit()
    return {
        "id": corr_id,
        "project_id": project_id,
        "old_memory_id": old_memory_id,
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
