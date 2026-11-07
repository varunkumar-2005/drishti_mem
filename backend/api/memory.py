"""
backend/api/memory.py
FastAPI router for memory operations scoped to a specific project.
Enforces strict project-level memory isolation.
"""

from __future__ import annotations

import hashlib
import re
from typing import List
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile

from backend.models.schemas import (
    AskRequest,
    AskResponse,
    CaptureRequest,
    CaptureResponse,
    ConflictCheckRequest,
    ConflictCheckResponse,
    ContextPackRequest,
    ContextPackResponse,
    CorrectRequest,
    CorrectResponse,
    IngestRequest,
    IngestResponse,
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
        old_memory_text=payload.old_memory_text or "",
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


def chunk_text(text: str, max_words: int = 500) -> List[str]:
    """
    Split text into chunks at paragraph or heading boundaries.
    Each chunk is roughly up to max_words.
    """
    if not text or not text.strip():
        return []

    normalized = text.replace("\r\n", "\n")
    raw_blocks = re.split(r'\n(?=(?:#{1,6}\s+))|\n\n+', normalized)

    chunks = []
    current_chunk = []
    current_word_count = 0

    for block in raw_blocks:
        block = block.strip()
        if not block:
            continue
        words = block.split()
        block_word_count = len(words)

        if current_word_count + block_word_count > max_words and current_chunk:
            chunks.append("\n\n".join(current_chunk).strip())
            current_chunk = []
            current_word_count = 0

        if block_word_count > max_words:
            for i in range(0, block_word_count, max_words):
                sub_words = words[i:i + max_words]
                chunks.append(" ".join(sub_words))
        else:
            current_chunk.append(block)
            current_word_count += block_word_count

    if current_chunk:
        chunks.append("\n\n".join(current_chunk).strip())

    return chunks


@router.post("/ingest", response_model=IngestResponse)
def ingest_text(
    project_id: str,
    payload: IngestRequest,
    memory_service=Depends(get_memory_service),
) -> IngestResponse:
    """
    Ingest a text/markdown document into project memory.
    Splits into ~500 word chunks at paragraph/heading boundaries.
    Idempotent: skips chunks that were already ingested.
    """
    project = get_project_or_404(project_id)
    bank_id = project["bank_id"]

    chunks = chunk_text(payload.text, max_words=500)
    retained_count = 0
    skipped_count = 0

    for chunk in chunks:
        ch_hash = hashlib.sha256(chunk.encode("utf-8")).hexdigest()
        if local_db.is_chunk_ingested(project_id, ch_hash):
            skipped_count += 1
            continue

        memory_service.retain(
            project_id=project_id,
            bank_id=bank_id,
            text=f"[{payload.source_name}] {chunk}",
            agent_id="ingest",
            source=payload.source_type,
            check_conflict=False,
        )
        local_db.record_ingested_chunk(
            project_id=project_id,
            content_hash=ch_hash,
            source_name=payload.source_name,
            source_type=payload.source_type,
            chunk_text=chunk,
        )
        retained_count += 1

    local_db.log_audit(
        project_id=project_id,
        agent_id="ingest",
        action="document_ingested",
        query_or_text=f"Ingested '{payload.source_name}' ({retained_count} chunks retained, {skipped_count} skipped)",
        result_count=len(chunks),
    )

    return IngestResponse(
        project_id=project_id,
        source_name=payload.source_name,
        source_type=payload.source_type,
        chunks_total=len(chunks),
        chunks_retained=retained_count,
        chunks_skipped=skipped_count,
        status="success",
    )


@router.post("/ingest-file", response_model=IngestResponse)
async def ingest_file(
    project_id: str,
    file: UploadFile = File(...),
    source_type: str = Form("doc"),
    memory_service=Depends(get_memory_service),
) -> IngestResponse:
    """Ingest an uploaded .md or .txt document into project memory."""
    project = get_project_or_404(project_id)
    filename = file.filename or "upload.txt"
    if not (filename.endswith(".md") or filename.endswith(".txt")):
        raise HTTPException(
            status_code=400,
            detail="Only .md and .txt files are supported for ingestion.",
        )

    content_bytes = await file.read()
    text = content_bytes.decode("utf-8", errors="replace")

    payload = IngestRequest(
        text=text,
        source_type=source_type,
        source_name=filename,
    )
    return ingest_text(project_id=project_id, payload=payload, memory_service=memory_service)


@router.post("/context-pack", response_model=ContextPackResponse)
def get_context_pack(
    project_id: str,
    payload: ContextPackRequest,
    memory_service=Depends(get_memory_service),
) -> ContextPackResponse:
    """
    Generate a compact, accurate context pack formatted for third-party AI assistants.
    Recalls relevant memories, excludes superseded ones, de-duplicates, and caps to max_chars.
    """
    project = get_project_or_404(project_id)
    bank_id = project["bank_id"]
    project_name = project.get("name", project_id)

    recalled = memory_service.recall(
        project_id=project_id,
        bank_id=bank_id,
        query=payload.task,
        max_results=15,
        include_superseded=False,
    )

    superseded_info = local_db.get_superseded_info(project_id)
    active_memories = []
    seen_texts = set()

    for m in recalled:
        m_id = m.get("id")
        m_text = m.get("text", "").strip()
        if not m_text:
            continue
        if m_id and m_id in superseded_info["ids"]:
            continue
        # Also check if text contains superseded signatures
        is_sup = False
        for old_txt in superseded_info["texts"]:
            if old_txt and (old_txt in m_text or m_text in old_txt):
                is_sup = True
                break
        if is_sup:
            continue

        norm = m_text.lower()
        if norm in seen_texts:
            continue
        seen_texts.add(norm)
        active_memories.append(m)

    target = payload.target.lower().strip()
    formatted_facts = []

    for m in active_memories:
        txt = m.get("text", "").strip()
        src = m.get("source") or (m.get("metadata", {}) or {}).get("source_name") or "doc"
        agent = m.get("agent_id") or "user"
        ts = m.get("timestamp") or ""
        date_str = ts.split("T")[0] if "T" in ts else ts or "recent"

        fact_line = f"- {txt} (source: {src}, by {agent}, {date_str})"
        formatted_facts.append((fact_line, m))

    def build_pack_text(facts_lines: List[str]) -> str:
        facts_block = "\n".join(facts_lines)
        if target == "cursor":
            return (
                f"# Cursor Project Rules: {project_name}\n"
                f"# Key decisions and facts relevant to: {payload.task}\n"
                f"{facts_block}\n"
                f"# END RULES\n\n"
                f"{payload.task}"
            )
        elif target == "claude":
            return (
                f"<project_context project=\"{project_name}\">\n"
                f"Key decisions and facts relevant to: {payload.task}\n"
                f"{facts_block}\n"
                f"</project_context>\n\n"
                f"{payload.task}"
            )
        else:
            return (
                f"[PROJECT CONTEXT: {project_name}]\n"
                f"Key decisions and facts relevant to: {payload.task}\n"
                f"{facts_block}\n"
                f"[END CONTEXT]\n\n"
                f"{payload.task}"
            )

    selected_lines = []
    selected_sources = []
    for line, mem in formatted_facts:
        candidate_lines = selected_lines + [line]
        candidate_pack = build_pack_text(candidate_lines)
        if len(candidate_pack) <= payload.max_chars:
            selected_lines.append(line)
            selected_sources.append(mem)
        else:
            break

    final_pack = build_pack_text(selected_lines)
    if len(final_pack) > payload.max_chars:
        final_pack = final_pack[:payload.max_chars]

    return ContextPackResponse(
        project_id=project_id,
        project_name=project_name,
        target=target,
        pack=final_pack,
        sources_used=selected_sources,
        char_count=len(final_pack),
        task=payload.task,
    )


@router.post("/capture", response_model=CaptureResponse)
def capture_decision(
    project_id: str,
    payload: CaptureRequest,
    memory_service=Depends(get_memory_service),
) -> CaptureResponse:
    """Capture a new decision with conflict detection against past memories."""
    project = get_project_or_404(project_id)
    bank_id = project["bank_id"]

    res = memory_service.retain(
        project_id=project_id,
        bank_id=bank_id,
        text=payload.text,
        agent_id="user",
        source="decision",
        check_conflict=True,
    )

    conflict_obj = res.get("conflict")
    has_conflict = False
    if conflict_obj:
        if isinstance(conflict_obj, dict):
            has_conflict = conflict_obj.get("has_conflict", False)
        elif hasattr(conflict_obj, "has_conflict"):
            has_conflict = conflict_obj.has_conflict

    return CaptureResponse(
        memory_id=res["memory_id"],
        project_id=project_id,
        source_name=payload.source_name,
        timestamp=res["timestamp"],
        conflict=conflict_obj,
        has_conflict=has_conflict,
    )
