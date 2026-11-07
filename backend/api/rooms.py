"""
backend/api/rooms.py
Endpoints for OneContext Live Team Rooms:
- Live Context Feed & Events
- Real-time Server-Sent Events (SSE) Stream
- Teammate Presence & Heartbeats
- AI Catch-up Summaries
- GitHub Repository Sync
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse

from backend.core.broadcaster import broadcaster
from backend.core.llm_client import LLMClient
from backend.models.schemas import (
    CatchUpRequest,
    CatchUpResponse,
    ContextPackRequest,
    ContextPackResponse,
    GitHubConfigRequest,
    GitHubConfigResponse,
    HeartbeatRequest,
    HeartbeatResponse,
    RoomEvent,
    RoomMemberItem,
)
from backend.services.github_sync import sync_repo_commits
from backend.storage import local_db

logger = logging.getLogger("onecontext.rooms")
router = APIRouter(tags=["Rooms"])


def get_llm_client(request: Request) -> LLMClient:
    return request.app.state.llm


def get_memory_service(request: Request):
    return request.app.state.memory_service


def get_team_or_404(team_id: str) -> Dict[str, Any]:
    team = local_db.get_team_by_id(team_id)
    if not team:
        # Check if caller passed join_code instead
        team = local_db.get_team_by_code(team_id.upper())
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Team room '{team_id}' not found.",
        )
    return team


# --- Live Context Events Feed ---

@router.get("/rooms/{team_id}/events", response_model=List[RoomEvent])
def get_room_events(
    team_id: str,
    since: Optional[str] = Query(default=None, description="ISO timestamp to filter newer events"),
    limit: int = Query(default=50, ge=1, le=200),
) -> List[RoomEvent]:
    """Return live context events for the team's project, newest first."""
    team = get_team_or_404(team_id)
    project_id = team["project_id"]
    if since:
        since = since.replace(" ", "+")
    events = local_db.get_events(project_id=project_id, since=since, limit=limit)
    return [RoomEvent(**e) for e in events]


# --- Server-Sent Events (SSE) Streaming ---

@router.get("/rooms/{team_id}/stream")
async def stream_room_events(team_id: str, request: Request):
    """
    Server-Sent Events endpoint pushing new live room events in real time.
    Falls back gracefully if the connection drops.
    """
    team = get_team_or_404(team_id)
    project_id = team["project_id"]
    queue = broadcaster.subscribe(project_id)

    async def event_generator():
        try:
            # Initial connection handshake
            yield f"event: connected\ndata: {json.dumps({'team_id': team_id, 'project_id': project_id, 'status': 'connected'})}\n\n"

            while True:
                # Check for client disconnect
                if await request.is_disconnected():
                    break

                try:
                    # Wait up to 15s for new event, otherwise send keep-alive ping
                    event_data = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield f"event: room_event\ndata: {json.dumps(event_data)}\n\n"
                except asyncio.TimeoutError:
                    yield f"event: ping\ndata: {json.dumps({'ping': datetime.now(timezone.utc).isoformat()})}\n\n"

        except asyncio.CancelledError:
            pass
        finally:
            broadcaster.unsubscribe(project_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# --- Presence & Heartbeats ---

@router.post("/rooms/{team_id}/heartbeat", response_model=HeartbeatResponse)
def member_heartbeat(team_id: str, payload: HeartbeatRequest) -> HeartbeatResponse:
    """Record a member heartbeat to mark them online (seen in last 60s)."""
    team = get_team_or_404(team_id)
    res = local_db.update_member_heartbeat(
        team_id=team["id"],
        display_name=payload.display_name.strip(),
    )
    return HeartbeatResponse(**res)


@router.get("/rooms/{team_id}/members", response_model=List[RoomMemberItem])
def get_room_members(team_id: str) -> List[RoomMemberItem]:
    """List all team members with online presence and last_seen timestamp."""
    team = get_team_or_404(team_id)
    members = local_db.list_room_members(team["id"])
    return [RoomMemberItem(**m) for m in members]


# --- Catch Me Up ---

@router.post("/rooms/{team_id}/catch-up", response_model=CatchUpResponse)
def catch_up_member(
    team_id: str,
    payload: CatchUpRequest,
    llm: LLMClient = Depends(get_llm_client),
) -> CatchUpResponse:
    """
    Summarize what changed since this member's last catch-up.
    Uses LLM at temperature 0 to produce a concise, strictly grounded summary
    grouped by decisions, architecture or doc changes, and commits.
    """
    team = get_team_or_404(team_id)
    project_id = team["project_id"]
    display_name = payload.display_name.strip()

    member = local_db.get_team_member(team["id"], display_name)
    last_catchup = member.get("last_seen_catchup") if member else None

    # Fetch events since last catchup, or recent 20 if first catch-up
    if last_catchup:
        events = local_db.get_events(project_id=project_id, since=last_catchup, limit=40)
    else:
        events = local_db.get_events(project_id=project_id, limit=20)

    # Convert to RoomEvent models
    event_models = [RoomEvent(**e) for e in events]

    if not event_models:
        return CatchUpResponse(
            summary="Nothing new since your last catch-up.",
            events=[],
            events_count=0,
        )

    # Format events for the LLM
    events_lines = []
    for e in reversed(event_models):  # Chronological order
        events_lines.append(
            f"- [{e.type.upper()}] {e.title} (by {e.author} at {e.created_at}): {e.body[:250]}"
        )
    events_block = "\n".join(events_lines)

    prompt = (
        f"You are a project catch-up assistant for room '{team['name']}'.\n"
        f"Summarize what changed based ONLY on the events below.\n\n"
        f"Group your summary into three sections:\n"
        f"1. Decisions\n"
        f"2. Architecture or doc changes\n"
        f"3. Commits\n\n"
        f"Strict rules:\n"
        f"- Keep names, numbers, and file names exact.\n"
        f"- Say nothing that is not in the events.\n"
        f"- If a section has no events, write 'None'.\n\n"
        f"Events:\n{events_block}"
    )

    try:
        summary, _ = llm.chat(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=600,
        )
    except Exception as ex:
        logger.error(f"Error calling LLM for catch-up: {ex}")
        summary = f"Recent activity:\n" + "\n".join([f"- {e.title}" for e in event_models[:5]])

    # Update member's catch-up timestamp
    local_db.update_member_catchup(team["id"], display_name)

    return CatchUpResponse(
        summary=summary,
        events=event_models,
        events_count=len(event_models),
    )


# --- Room Context Pack Proxy ---

@router.post("/rooms/{team_id}/context-pack", response_model=ContextPackResponse)
def get_room_context_pack(
    team_id: str,
    payload: ContextPackRequest,
    memory_service=Depends(get_memory_service),
) -> ContextPackResponse:
    """Generate a context pack scoped to the room's project."""
    team = get_team_or_404(team_id)
    project_id = team["project_id"]
    from backend.api.memory import get_context_pack
    return get_context_pack(project_id=project_id, payload=payload, memory_service=memory_service)


# --- GitHub Sync Endpoints ---

@router.post("/projects/{project_id}/github", response_model=GitHubConfigResponse)
async def configure_github(
    project_id: str,
    payload: GitHubConfigRequest,
    memory_service=Depends(get_memory_service),
) -> GitHubConfigResponse:
    """Configure GitHub repo for project and run initial commit synchronization."""
    repo = payload.repo.strip()
    cfg = local_db.save_project_github(project_id, repo)
    # Trigger initial sync in background
    asyncio.create_task(sync_repo_commits(project_id, repo, memory_service=memory_service))
    return GitHubConfigResponse(**cfg)


@router.get("/projects/{project_id}/github", response_model=GitHubConfigResponse)
def get_github_config(project_id: str) -> GitHubConfigResponse:
    """Get GitHub configuration and last sync status."""
    cfg = local_db.get_project_github(project_id)
    if not cfg:
        return GitHubConfigResponse(project_id=project_id, repo="", last_status="not_configured")
    return GitHubConfigResponse(**cfg)


@router.post("/projects/{project_id}/github/sync")
async def manual_github_sync(
    project_id: str,
    memory_service=Depends(get_memory_service),
):
    """Trigger manual GitHub synchronization now."""
    cfg = local_db.get_project_github(project_id)
    if not cfg or not cfg.get("repo"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GitHub repo not configured for this project.",
        )
    result = await sync_repo_commits(project_id, cfg["repo"], memory_service=memory_service)
    return result


@router.post("/webhooks/github")
async def github_webhook(request: Request, memory_service=Depends(get_memory_service)):
    """Handle incoming GitHub push webhooks."""
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    repo_info = payload.get("repository", {})
    full_name = repo_info.get("full_name", "")
    commits = payload.get("commits", [])

    if not full_name:
        return {"status": "ignored", "reason": "No repository full_name"}

    # Find which project uses this repo
    all_projects = local_db.list_all_github_projects()
    matched = [p for p in all_projects if p["repo"].lower() == full_name.lower()]
    if not matched:
        return {"status": "ignored", "reason": f"Repo '{full_name}' not connected to any project"}

    for p in matched:
        project_id = p["project_id"]
        await sync_repo_commits(project_id, full_name, memory_service=memory_service)

    return {"status": "success", "processed_projects": len(matched)}
