"""
backend/api/projects.py
FastAPI router for project management.
Each project creates and owns one isolated Hindsight memory bank.
"""

from __future__ import annotations

import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Request

from backend.models.schemas import ProjectCreate, ProjectResponse
from backend.storage import local_db

router = APIRouter(prefix="/projects", tags=["Projects"])


def get_memory_service(request: Request):
    return request.app.state.memory_service


@router.post("", response_model=ProjectResponse, status_code=201)
def create_project(
    payload: ProjectCreate,
    memory_service=Depends(get_memory_service),
) -> ProjectResponse:
    """Create a new project and initialize its isolated Hindsight memory bank."""
    project_id = str(uuid.uuid4())[:8]
    bank_id = f"onecontext-{project_id}"

    # Provision isolated memory bank in Hindsight
    success = memory_service.hindsight.create_bank(
        bank_id=bank_id,
        name=payload.name,
        mission=payload.description or f"Memory bank for project {payload.name}",
    )
    if not success:
        raise HTTPException(status_code=500, detail="Failed to provision memory bank in Hindsight")

    # Store project in local SQLite
    project_record = local_db.create_project(
        project_id=project_id,
        name=payload.name,
        description=payload.description,
        bank_id=bank_id,
    )

    return ProjectResponse(**project_record)


@router.get("", response_model=List[ProjectResponse])
def list_projects() -> List[ProjectResponse]:
    """List all registered projects."""
    projects = local_db.list_projects()
    return [ProjectResponse(**p) for p in projects]
