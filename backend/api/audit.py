"""
backend/api/audit.py
FastAPI router for project audit trail and memory history.
"""

from __future__ import annotations

from typing import List
from fastapi import APIRouter, HTTPException

from backend.models.schemas import AuditEntry
from backend.storage import local_db

router = APIRouter(prefix="/projects/{project_id}/audit", tags=["Audit"])


@router.get("", response_model=List[AuditEntry])
def get_project_audit(
    project_id: str,
    limit: int = 50,
) -> List[AuditEntry]:
    """Retrieve the chronological audit trail of retain, recall, and validate events."""
    project = local_db.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found.")

    entries = local_db.get_audit(project_id=project_id, limit=limit)
    return [AuditEntry(**e) for e in entries]
