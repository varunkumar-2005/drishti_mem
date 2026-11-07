"""
backend/api/teams.py
Team Room endpoints with 6-character join codes.
"""

from __future__ import annotations

import logging
from typing import List
from fastapi import APIRouter, HTTPException, Request, status

from backend.agents.validator_agent import ValidatorAgent
from backend.models.schemas import (
    TeamCreate,
    TeamResponse,
    TeamJoinRequest,
    TeamJoinResponse,
    TeamMemberResponse,
    TeamMessageCreate,
    TeamMessageResponse,
    TeamCodeActionRequest,
    TeamCodeActionResponse,
)
from backend.core.broadcaster import broadcaster
from backend.storage import local_db

logger = logging.getLogger("onecontext.teams")
router = APIRouter(prefix="/teams", tags=["Teams"])


@router.post("", response_model=TeamResponse, status_code=status.HTTP_201_CREATED)
def create_team(payload: TeamCreate) -> TeamResponse:
    """Create a new team room with a unique 6-character join code."""
    # Ensure project exists
    project = local_db.get_project(payload.project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{payload.project_id}' not found.",
        )

    team = local_db.create_team(
        name=payload.name,
        project_id=payload.project_id,
    )

    # Log to audit trail
    local_db.log_audit(
        project_id=payload.project_id,
        agent_id="system",
        action="team_created",
        query_or_text=f"Team '{team['name']}' created with join code {team['join_code']}",
    )

    return TeamResponse(**team)


@router.post("/join", response_model=TeamJoinResponse)
def join_team(payload: TeamJoinRequest) -> TeamJoinResponse:
    """Join a team room using a 6-character join code."""
    code = payload.join_code.strip().upper()
    team = local_db.get_team_by_code(code)
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Invalid join code '{code}'. Team room not found.",
        )

    member = local_db.add_team_member(
        team_id=team["id"],
        display_name=payload.display_name,
    )

    # Log to audit trail
    local_db.log_audit(
        project_id=team["project_id"],
        agent_id=payload.display_name.strip(),
        action="member_joined",
        query_or_text=f"Member '{payload.display_name.strip()}' joined team '{team['name']}' (code {team['join_code']})",
    )

    # Record event in live room feed
    join_event = local_db.record_event(
        project_id=team["project_id"],
        type="member_joined",
        title=f"{payload.display_name.strip()} joined the room",
        body=f"Joined team '{team['name']}' with join code {team['join_code']}",
        author=payload.display_name.strip(),
    )
    if join_event:
        broadcaster.publish_nowait(team["project_id"], join_event)

    return TeamJoinResponse(
        team=TeamResponse(**team),
        project_id=team["project_id"],
        member=TeamMemberResponse(**member),
    )


@router.get("/{team_id}/members", response_model=List[TeamMemberResponse])
def get_team_members(team_id: str) -> List[TeamMemberResponse]:
    """List all members of a team room."""
    team = local_db.get_team_by_id(team_id)
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Team '{team_id}' not found.",
        )

    members = local_db.list_team_members(team_id)
    return [TeamMemberResponse(**m) for m in members]


@router.post("/{team_id}/messages", response_model=TeamMessageResponse)
def post_team_message(team_id: str, payload: TeamMessageCreate, request: Request) -> TeamMessageResponse:
    """Send a real-time message or broadcast a logic change to the team room."""
    team = local_db.get_team_by_id(team_id)
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Team '{team_id}' not found.",
        )

    # 1. Store in SQLite
    msg = local_db.add_team_message(
        team_id=team_id,
        sender=payload.sender,
        role=payload.role,
        message=payload.message,
        message_type=payload.message_type,
    )

    # 2. Retain as memory if requested or marked as decision/code_change
    should_retain = payload.retain_as_memory or payload.message_type in ("decision", "code_change")
    if should_retain and hasattr(request.app.state, "memory_service"):
        try:
            mem_service = request.app.state.memory_service
            project = local_db.get_project(team["project_id"])
            if project:
                bank_id = project["bank_id"]
                prefix = f"[{payload.role.upper()} UPDATE by {payload.sender}] "
                mem_service.retain(
                    project_id=team["project_id"],
                    bank_id=bank_id,
                    text=f"{prefix}{payload.message}",
                    agent_id=payload.sender,
                    source="team_broadcast",
                    check_conflict=False,
                )
                local_db.log_audit(
                    project_id=team["project_id"],
                    agent_id=payload.sender,
                    action="team_logic_broadcast",
                    query_or_text=payload.message,
                )
        except Exception as exc:
            logger.warning(f"Failed to index team message to memory: {exc}")

    # 3. If someone asks @agent or asks a technical question, automatically trigger Copilot Agent to reply in chat!
    msg_clean = payload.message.strip().lower()
    is_agent_query = (
        "@agent" in msg_clean
        or "?" in msg_clean
        or any(msg_clean.startswith(w) for w in ["what", "how", "why", "who", "where", "can we", "is there", "tell me", "explain"])
    )
    if is_agent_query and hasattr(request.app.state, "memory_service"):
        try:
            mem_service = request.app.state.memory_service
            project = local_db.get_project(team["project_id"])
            if project:
                clean_query = payload.message.replace("@agent", "").replace("@Agent", "").strip()
                ans = mem_service.ask(
                    project_id=team["project_id"],
                    bank_id=project["bank_id"],
                    question=clean_query,
                    agent_id="agent-copilot",
                )
                local_db.add_team_message(
                    team_id=team_id,
                    sender="OneContext Copilot",
                    role="agent",
                    message=ans.get("answer", "No context found in project memory."),
                    message_type="alert",
                )
        except Exception as exc:
            logger.warning(f"Copilot auto-reply failed: {exc}")

    return TeamMessageResponse(**msg)


@router.get("/{team_id}/messages", response_model=List[TeamMessageResponse])
def get_team_messages(team_id: str, limit: int = 100) -> List[TeamMessageResponse]:
    """Get chronological message stream for the team room."""
    team = local_db.get_team_by_id(team_id)
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Team '{team_id}' not found.",
        )
    messages = local_db.list_team_messages(team_id, limit=limit)
    return [TeamMessageResponse(**m) for m in messages]


@router.post("/{team_id}/seed-demo")
def seed_demo_collaborators(team_id: str) -> dict:
    """Pre-populate 4 active team collaborators and starter war-room context for live demo."""
    team = local_db.get_team_by_id(team_id)
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Team '{team_id}' not found.",
        )

    # 4 Team members
    teammates = [
        ("Varun", "Lead Architect"),
        ("Alice", "Auth & Security Specialist"),
        ("Bob", "Backend Systems Engineer"),
        ("Validator Agent", "Automated Policy Guardrail"),
    ]

    existing_members = {m["display_name"] for m in local_db.list_team_members(team_id)}
    for name, _ in teammates:
        if name not in existing_members:
            local_db.add_team_member(team_id=team_id, display_name=name)

    # Initial war room messages if empty
    existing_msgs = local_db.list_team_messages(team_id, limit=5)
    if len(existing_msgs) == 0:
        starter_messages = [
            ("Varun", "architect", "Team assembled! We are working on the authentication microservice in parallel. All login changes must follow our Zero-Trust ADRs.", "chat"),
            ("Alice", "security", "Hey team! I have active tabs open on auth/login_service.py. If I update any token or session rules, I'll broadcast directly to our memory bank.", "chat"),
            ("Bob", "backend", "Connected! I am building the downstream user profile endpoint expecting standard RS256 JWT claims from auth.", "chat"),
            ("Validator Agent", "agent", "🛡️ Guardrail active. Monitoring PR drafts against project institutional memory.", "alert"),
        ]
        for sender, role, msg, mtype in starter_messages:
            local_db.add_team_message(team_id, sender, msg, role=role, message_type=mtype)

    return {"status": "ok", "message": "Demo team of 4 assembled."}


@router.post("/{team_id}/generate-code", response_model=TeamCodeActionResponse)
def generate_team_code(team_id: str, payload: TeamCodeActionRequest, request: Request) -> TeamCodeActionResponse:
    """Live LLM code synthesis with institutional memory grounding and automated validator check."""
    team = local_db.get_team_by_id(team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team room not found.")

    project = local_db.get_project(team["project_id"])
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    bank_id = project["bank_id"]
    mem_service = request.app.state.memory_service
    llm = request.app.state.llm

    # 1. Recall relevant institutional memory
    recalled = mem_service.recall(
        project_id=team["project_id"],
        bank_id=bank_id,
        query=f"{payload.filename} {payload.instruction}",
        max_results=5,
    )

    context_lines = []
    for m in recalled:
        if isinstance(m, dict):
            src = m.get("source", "ADR")
            txt = m.get("text", "")
            context_lines.append(f"- [{src}]: {txt}")
    context_str = "\n".join(context_lines)

    # 2. Call Groq LLM to synthesize updated code
    prompt = f"""You are an expert autonomous software engineer working in a live team room.
Modifying file: {payload.filename}
AUTHOR: {payload.author}

TASK / INSTRUCTION:
{payload.instruction}

INSTITUTIONAL MEMORY POLICIES (MANDATORY ARCHITECTURAL RULES):
{context_str or "Adhere to standard enterprise security best practices: RS256 JWT, short expiry, no plain session cookies."}

CURRENT CODE:
```python
{payload.current_code}
```

REQUIREMENTS:
1. Rewrite the code to implement the requested instruction cleanly.
2. Put the full rewritten Python code inside a ```python ... ``` block.
3. Below the code block, provide a clear 2-sentence explanation of what was changed and which memory rules were satisfied.
"""
    raw_response, model_used = llm.chat(
        messages=[
            {"role": "system", "content": "You are an autonomous coding assistant grounded in persistent team memory."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        max_tokens=1500,
    )

    new_code = payload.current_code
    explanation = raw_response
    if "```python" in raw_response:
        parts = raw_response.split("```python")
        code_part = parts[1].split("```")[0]
        new_code = code_part.strip()
        explanation = raw_response.replace(f"```python{code_part}```", "").strip()
    elif "```" in raw_response:
        parts = raw_response.split("```")
        new_code = parts[1].strip()
        explanation = (parts[0] + "\n" + "".join(parts[2:])).strip()

    # 3. Live Guardrail Check with the Validator Agent!
    validator = ValidatorAgent(
        project_id=team["project_id"],
        bank_id=bank_id,
        memory_service=mem_service,
    )
    val_res = validator.validate(
        draft_text=new_code,
        check_topic=f"{payload.filename} {payload.instruction}",
    )

    # 4. Broadcast live update to team chat
    status_icon = "✅" if val_res["valid"] else "❌"
    broadcast_msg = f"⚡ [{payload.author}] Prompted: \"{payload.instruction}\"\n\n{status_icon} Validator Guardrail: {'PASSED (Zero Regressions)' if val_res['valid'] else 'CONTRADICTION DETECTED'}\n\n{explanation}"
    if not val_res["valid"] and val_res["contradictions"]:
        broadcast_msg += "\n\n⚠️ Violations Flagged:\n" + "\n".join([f"- {c}" for c in val_res["contradictions"]])

    local_db.add_team_message(
        team_id=team_id,
        sender=payload.author,
        role="coder",
        message=broadcast_msg,
        message_type="code_change",
    )

    # If valid, retain the decision into Hindsight!
    if val_res["valid"]:
        try:
            mem_service.retain(
                project_id=team["project_id"],
                bank_id=bank_id,
                text=f"Decision by {payload.author} on {payload.filename}: {payload.instruction}. {explanation[:180]}",
                agent_id=payload.author,
                source="team_code_synthesis",
                check_conflict=False,
            )
        except Exception:
            pass

    return TeamCodeActionResponse(
        new_code=new_code,
        explanation=explanation,
        memories_recalled=[m if isinstance(m, dict) else dict(m) for m in recalled],
        validation=val_res,
        status="success",
    )
