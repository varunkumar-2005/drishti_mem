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
    ConflictCheckRequest,
    ConflictCheckResponse,
    CorrectRequest,
    CorrectResponse,
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
    """Store a fact, decision, or note in this project's isolated memory bank, checking for conflicts."""
    project = get_project_or_404(project_id)
    bank_id = project["bank_id"]

    result = memory_service.retain(
        project_id=project_id,
        bank_id=bank_id,
        text=payload.text,
        agent_id=payload.agent_id,
        source=payload.source,
        check_conflict=payload.check_conflict,
    )
    return RetainResponse(**result)


@router.post("/correct", response_model=CorrectResponse)
def correct_memory(
    project_id: str,
    payload: CorrectRequest,
    memory_service=Depends(get_memory_service),
) -> CorrectResponse:
    """Correct and supersede an outdated or inaccurate memory entry."""
    project = get_project_or_404(project_id)
    bank_id = project["bank_id"]

    result = memory_service.correct(
        project_id=project_id,
        bank_id=bank_id,
        old_memory_id=payload.old_memory_id,
        new_text=payload.new_text,
        agent_id=payload.agent_id,
        reason=payload.reason,
    )
    return CorrectResponse(**result)


@router.post("/check-conflict", response_model=ConflictCheckResponse)
def check_conflict(
    project_id: str,
    payload: ConflictCheckRequest,
    memory_service=Depends(get_memory_service),
) -> ConflictCheckResponse:
    """Cross-check proposed text against active project memories to detect conflicts without retaining."""
    project = get_project_or_404(project_id)
    bank_id = project["bank_id"]

    existing = memory_service.recall(
        project_id=project_id,
        bank_id=bank_id,
        query=payload.text,
        max_results=4,
        include_superseded=False,
    )
    detected = memory_service.conflict_detector.detect_conflict(payload.text, existing)
    return ConflictCheckResponse(
        has_conflict=detected["has_conflict"],
        conflict=detected if detected["has_conflict"] else None,
    )


@router.get("/conflicts")
def get_detected_conflicts(project_id: str) -> dict:
    """Retrieve all conflict detection events logged in the project audit log."""
    get_project_or_404(project_id)
    audit = local_db.get_audit(project_id, limit=100)
    conflict_events = [a for a in audit if a["action"] == "conflict_detected"]
    corrections = local_db.get_corrections(project_id)
    return {
        "project_id": project_id,
        "conflicts": conflict_events,
        "corrections": corrections,
    }


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
        include_superseded=payload.include_superseded,
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
