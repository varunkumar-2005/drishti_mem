"""
backend/api/agents.py
FastAPI router for agent registration, multi-agent runs, and validation.
"""

from __future__ import annotations

import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Request

from backend.agents.agent_one import PlannerAgent
from backend.agents.agent_two import BuilderAgent
from backend.agents.validator_agent import ValidatorAgent
from backend.models.schemas import (
    AgentRegister,
    AgentResponse,
    AgentRunRequest,
    AgentRunResponse,
    MemoryItem,
    ValidateRequest,
    ValidateResponse,
)
from backend.storage import local_db

router = APIRouter(prefix="/projects/{project_id}", tags=["Agents"])


def get_memory_service(request: Request):
    return request.app.state.memory_service


def get_project_or_404(project_id: str) -> dict:
    project = local_db.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found.")
    return project


@router.post("/agents", response_model=AgentResponse, status_code=201)
def register_agent(
    project_id: str,
    payload: AgentRegister,
) -> AgentResponse:
    """Register an agent for a project."""
    get_project_or_404(project_id)
    agent_id = payload.id or f"agent-{uuid.uuid4().hex[:6]}"

    record = local_db.register_agent(
        agent_id=agent_id,
        project_id=project_id,
        name=payload.name,
        role=payload.role,
    )
    return AgentResponse(**record)


@router.get("/agents", response_model=List[AgentResponse])
def list_agents(project_id: str) -> List[AgentResponse]:
    """List all agents registered for this project."""
    get_project_or_404(project_id)
    agents = local_db.list_agents(project_id)
    return [AgentResponse(**a) for a in agents]


@router.post("/agents/{agent_id}/run", response_model=AgentRunResponse)
def run_agent(
    project_id: str,
    agent_id: str,
    payload: AgentRunRequest,
    memory_service=Depends(get_memory_service),
) -> AgentRunResponse:
    """
    Run an agent task. Dynamically dispatches to Planner, Builder, or BaseAgent
    sharing this project's isolated Hindsight memory bank.
    """
    project = get_project_or_404(project_id)
    bank_id = project["bank_id"]

    agent_record = local_db.get_agent(agent_id=agent_id, project_id=project_id)
    role = agent_record["role"] if agent_record else "General Agent"

    # Dispatch by role or agent_id
    role_lower = (role or "").lower()
    id_lower = agent_id.lower()

    if "planner" in role_lower or "planner" in id_lower or "architect" in role_lower:
        planner = PlannerAgent(
            project_id=project_id,
            bank_id=bank_id,
            memory_service=memory_service,
            agent_id=agent_id,
        )
        res = planner.plan_and_retain(task=payload.task, context=payload.context or "")
        return AgentRunResponse(
            agent_id=agent_id,
            role=planner.role,
            project_id=project_id,
            output=res["output"],
            memories_recalled=[MemoryItem(**m) for m in res["memories_recalled"]],
            memories_retained=res["decisions_retained"],
        )

    elif "builder" in role_lower or "builder" in id_lower or "coder" in role_lower:
        builder = BuilderAgent(
            project_id=project_id,
            bank_id=bank_id,
            memory_service=memory_service,
            agent_id=agent_id,
        )
        res = builder.build_guidance(task=payload.task, context=payload.context or "")
        return AgentRunResponse(
            agent_id=agent_id,
            role=builder.role,
            project_id=project_id,
            output=res["output"],
            memories_recalled=[MemoryItem(**m) for m in res["memories_recalled"]],
            memories_retained=res["decisions_retained"],
        )

    else:
        # Generic agent grounded execution
        res = memory_service.ask(
            project_id=project_id,
            bank_id=bank_id,
            question=payload.task,
            agent_id=agent_id,
        )
        return AgentRunResponse(
            agent_id=agent_id,
            role=role,
            project_id=project_id,
            output=res["answer"],
            memories_recalled=[MemoryItem(**m) for m in res["sources"]],
            memories_retained=[],
        )


@router.post("/validate", response_model=ValidateResponse)
def validate_draft(
    project_id: str,
    payload: ValidateRequest,
    memory_service=Depends(get_memory_service),
) -> ValidateResponse:
    """
    Validator agent checks a proposed draft against recalled memories
    from the project's Hindsight bank and reports contradictions.
    """
    project = get_project_or_404(project_id)
    bank_id = project["bank_id"]

    validator = ValidatorAgent(
        project_id=project_id,
        bank_id=bank_id,
        memory_service=memory_service,
    )

    res = validator.validate(draft_text=payload.draft, check_topic=payload.check_topic)

    citations = [MemoryItem(**m) for m in res["citations"]]

    return ValidateResponse(
        valid=res["valid"],
        analysis=res["analysis"],
        contradictions=res["contradictions"],
        citations=citations,
        project_id=project_id,
    )
