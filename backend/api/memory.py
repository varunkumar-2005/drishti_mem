"""
backend/api/memory.py
FastAPI router for memory operations scoped to a specific project.
Enforces strict project-level memory isolation.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from backend.models.schemas import (
    AskRequest,
    AskResponse,
    MemoryItem,
    RecallRequest,
    RecallResponse,
    RetainRequest,
    RetainResponse,
)
from backend.storage import local_db

router = APIRouter(prefix="/projects/{project_id}", tags=["Memory"])


def get_memory_service(request: Request):
    return request.app.state.memory_service


def get_project_or_404(project_id: str) -> dict:
    """Ensure project exists and retrieve its secure bank_id."""
    project = local_db.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found.")
    return project


@router.post("/retain", response_model=RetainResponse)
def retain_memory(
    project_id: str,
    payload: RetainRequest,
    memory_service=Depends(get_memory_service),
) -> RetainResponse:
    """Store a fact, decision, or note in this project's isolated memory bank."""
    project = get_project_or_404(project_id)
    bank_id = project["bank_id"]

    result = memory_service.retain(
        project_id=project_id,
        bank_id=bank_id,
        text=payload.text,
        agent_id=payload.agent_id,
        source=payload.source,
    )
    return RetainResponse(**result)


@router.post("/recall", response_model=RecallResponse)
def recall_memory(
    project_id: str,
    payload: RecallRequest,
    memory_service=Depends(get_memory_service),
) -> RecallResponse:
    """Recall relevant memories for a query from this project's bank."""
    project = get_project_or_404(project_id)
    bank_id = project["bank_id"]

    results = memory_service.recall(
        project_id=project_id,
        bank_id=bank_id,
        query=payload.query,
        max_results=payload.max_results,
    )
    items = [MemoryItem(**r) for r in results]
    return RecallResponse(query=payload.query, results=items, project_id=project_id)


@router.post("/ask", response_model=AskResponse)
def ask_with_memory(
    project_id: str,
    payload: AskRequest,
    memory_service=Depends(get_memory_service),
) -> AskResponse:
    """Answer a question grounded in recalled project memory (RAG)."""
    project = get_project_or_404(project_id)
    bank_id = project["bank_id"]

    result = memory_service.ask(
        project_id=project_id,
        bank_id=bank_id,
        question=payload.question,
        agent_id=payload.agent_id,
    )
    return AskResponse(**result)


@router.post("/ask-without-memory", response_model=AskResponse)
def ask_without_memory(
    project_id: str,
    payload: AskRequest,
    memory_service=Depends(get_memory_service),
) -> AskResponse:
    """Answer a question WITHOUT memory (for Before/After comparison)."""
    # Verify project exists for route consistency
    get_project_or_404(project_id)

    result = memory_service.ask_without_memory(
        question=payload.question,
        agent_id=payload.agent_id,
    )
    return AskResponse(**result)
