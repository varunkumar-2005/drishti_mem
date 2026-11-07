"""
backend/models/schemas.py
Pydantic v2 request/response schemas for the OneContext API.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# --- Project Models ---
class ProjectCreate(BaseModel):
    name: str = Field(..., description="Name of the project")
    description: str = Field(default="", description="Project mission or description")


class ProjectResponse(BaseModel):
    id: str
    name: str
    description: str
    bank_id: str
    created_at: str


# --- Memory Models ---
class ConflictDetail(BaseModel):
    has_conflict: bool
    conflicting_memory: Optional[Dict[str, Any]] = None
    explanation: Optional[str] = None
    new_text: Optional[str] = None


class RetainRequest(BaseModel):
    text: str = Field(..., description="Fact, decision, or architectural note to retain")
    source: str = Field(default="note", description="Source type: note, decision, chat, doc, incident")
    agent_id: str = Field(default="user", description="Author agent ID or user ID")
    check_conflict: bool = Field(default=True, description="Whether to check for policy conflicts upon retain")


class RetainResponse(BaseModel):
    memory_id: str
    project_id: str
    agent_id: str
    source: str
    timestamp: str
    conflict: Optional[ConflictDetail] = None
    supersedes: Optional[str] = None


class CorrectRequest(BaseModel):
    old_memory_id: str = Field(..., description="ID of memory being superseded")
    new_text: str = Field(..., description="Updated and corrected memory text")
    agent_id: str = Field(default="user", description="Author agent ID")
    reason: str = Field(default="", description="Reason for the correction")
    old_memory_text: Optional[str] = Field(default="", description="Original memory text to exclude derived facts")


class CorrectResponse(BaseModel):
    memory_id: str
    old_memory_id: str
    supersedes: str
    project_id: str
    reason: str
    timestamp: str
    status: str = "corrected"


class ConflictCheckRequest(BaseModel):
    text: str = Field(..., description="Text to cross-check against recorded memories for contradiction")


class ConflictCheckResponse(BaseModel):
    has_conflict: bool
    conflict: Optional[ConflictDetail] = None


class RecallRequest(BaseModel):
    query: str = Field(..., description="Semantic search query")
    max_results: int = Field(default=5, ge=1, le=20)
    include_superseded: bool = Field(default=True, description="Whether to include superseded historical memories")


class MemoryItem(BaseModel):
    id: str
    text: str
    type: Optional[str] = None
    source: Optional[str] = None
    agent_id: Optional[str] = None
    timestamp: Optional[str] = None
    score: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None
    supersedes: Optional[str] = None
    is_superseded: Optional[bool] = False


class RecallResponse(BaseModel):
    query: str
    results: List[MemoryItem]
    project_id: str


class AskRequest(BaseModel):
    question: str = Field(..., description="Question to answer using recalled memories")
    agent_id: str = Field(default="user", description="Requesting agent or user ID")


class AskResponse(BaseModel):
    model_config = {"protected_namespaces": ()}

    question: str
    answer: str
    sources: List[MemoryItem]
    project_id: Optional[str] = None
    model_used: str


# --- Agent Models ---
class AgentRegister(BaseModel):
    id: Optional[str] = Field(default=None, description="Optional custom agent ID (e.g. agent-planner)")
    name: str = Field(..., description="Agent display name")
    role: str = Field(default="", description="Role or specialization (e.g. Planner, Builder, Validator)")


class AgentResponse(BaseModel):
    id: str
    project_id: str
    name: str
    role: str
    created_at: str


class AgentRunRequest(BaseModel):
    task: str = Field(..., description="Task or prompt to execute with this agent")
    context: Optional[str] = Field(default="", description="Additional optional contextual details")


class AgentRunResponse(BaseModel):
    agent_id: str
    role: str
    project_id: str
    output: str
    memories_recalled: List[MemoryItem] = []
    memories_retained: List[str] = []


# --- Validation Models ---
class ValidateRequest(BaseModel):
    draft: str = Field(..., description="Proposed decision, code snippet, or document to validate against memory")
    check_topic: Optional[str] = Field(default=None, description="Optional topic hint for memory retrieval")


class ValidateResponse(BaseModel):
    valid: bool
    analysis: str
    contradictions: List[str]
    citations: List[MemoryItem]
    project_id: str


# --- Audit Models ---
class AuditEntry(BaseModel):
    id: str
    project_id: str
    agent_id: str
    action: str
    query_or_text: Optional[str] = None
    result_count: int
    timestamp: str


# --- Health & Error ---
class HealthResponse(BaseModel):
    status: str
    hindsight: str
    groq: str


class ErrorResponse(BaseModel):
    error: str
    detail: str = ""


# --- Team Room Models ---
class TeamCreate(BaseModel):
    name: str = Field(..., description="Name of the team room")
    project_id: str = Field(..., description="Project ID associated with this team room")


class TeamResponse(BaseModel):
    id: str
    name: str
    join_code: str
    project_id: str
    created_at: str


class TeamJoinRequest(BaseModel):
    join_code: str = Field(..., description="6-character alphanumeric join code")
    display_name: str = Field(..., description="Name of the team member joining")


class TeamMemberResponse(BaseModel):
    team_id: str
    display_name: str
    joined_at: str


class TeamJoinResponse(BaseModel):
    team: TeamResponse
    project_id: str
    member: TeamMemberResponse


class TeamMessageCreate(BaseModel):
    sender: str = Field(..., description="Name of the team member or agent sending the message")
    role: str = Field(default="developer", description="Role: architect, frontend, backend, validator, etc.")
    message: str = Field(..., description="Message text or code update description")
    message_type: str = Field(default="chat", description="Type: chat, decision, code_change, alert")
    retain_as_memory: bool = Field(default=False, description="Whether to also index this into project Hindsight memory")


class TeamMessageResponse(BaseModel):
    id: str
    team_id: str
    sender: str
    role: str
    message: str
    message_type: str
    timestamp: str


class TeamCodeActionRequest(BaseModel):
    instruction: str = Field(..., description="Prompt or instruction for changing the code")
    current_code: str = Field(..., description="Existing code in the active editor")
    filename: str = Field(default="auth/login_service.py", description="Name of the file being edited")
    author: str = Field(default="Alice (Auth)", description="Developer or agent making the change")


class TeamCodeActionResponse(BaseModel):
    new_code: str
    explanation: str
    memories_recalled: List[Dict[str, Any]] = []
    validation: Dict[str, Any]
    status: str = "success"


# --- Context Pack, Ingestion, and Capture Models ---
class IngestRequest(BaseModel):
    text: str = Field(..., description="Document text or markdown to ingest")
    source_type: str = Field(default="doc", description="Source type: doc | decision | chat_export | note")
    source_name: str = Field(..., description="Filename or identifier for the source")


class IngestResponse(BaseModel):
    project_id: str
    source_name: str
    source_type: str
    chunks_total: int
    chunks_retained: int
    chunks_skipped: int
    status: str = "success"


class ContextPackRequest(BaseModel):
    task: str = Field(..., description="Task or prompt the assistant will perform")
    target: str = Field(default="generic", description="Target assistant: chatgpt | claude | cursor | codex | generic")
    max_chars: int = Field(default=3000, ge=100, description="Maximum characters allowed in the context pack")


class ContextPackResponse(BaseModel):
    project_id: str
    project_name: str
    target: str
    pack: str
    sources_used: List[Dict[str, Any]] = []
    char_count: int
    task: str


class CaptureRequest(BaseModel):
    text: str = Field(..., description="Decision or fact to capture")
    source_name: str = Field(default="manual_capture", description="Name/source identifier")


class CaptureResponse(BaseModel):
    memory_id: str
    project_id: str
    source_name: str
    timestamp: str
    conflict: Optional[ConflictDetail] = None
    has_conflict: bool = False



