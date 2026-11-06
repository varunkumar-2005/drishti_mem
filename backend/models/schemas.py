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
class RetainRequest(BaseModel):
    text: str = Field(..., description="Fact, decision, or architectural note to retain")
    source: str = Field(default="note", description="Source type: note, decision, chat, doc, incident")
    agent_id: str = Field(default="user", description="Author agent ID or user ID")


class RetainResponse(BaseModel):
    memory_id: str
    project_id: str
    agent_id: str
    source: str
    timestamp: str


class RecallRequest(BaseModel):
    query: str = Field(..., description="Semantic search query")
    max_results: int = Field(default=5, ge=1, le=20)


class MemoryItem(BaseModel):
    id: str
    text: str
    type: Optional[str] = None
    source: Optional[str] = None
    agent_id: Optional[str] = None
    timestamp: Optional[str] = None
    score: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None


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


# --- Health & Error ---
class HealthResponse(BaseModel):
    status: str
    hindsight: str
    groq: str


class ErrorResponse(BaseModel):
    error: str
    detail: str = ""
