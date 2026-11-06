"""
backend/agents/base_agent.py
Base agent class for all OneContext agents.
Provides unified access to shared project memory via MemoryService.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from backend.core.memory_service import MemoryService


class BaseAgent:
    """Base class for autonomous project agents sharing a single Hindsight memory bank."""

    def __init__(
        self,
        agent_id: str,
        role: str,
        project_id: str,
        bank_id: str,
        memory_service: MemoryService,
    ):
        self.agent_id = agent_id
        self.role = role
        self.project_id = project_id
        self.bank_id = bank_id
        self.memory_service = memory_service

    def retain(self, text: str, source: str = "decision") -> Dict[str, Any]:
        """Retain a memory in the shared bank, automatically stamped with this agent's ID."""
        return self.memory_service.retain(
            project_id=self.project_id,
            bank_id=self.bank_id,
            text=text,
            agent_id=self.agent_id,
            source=source,
        )

    def recall(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """Recall relevant memories from the shared bank."""
        return self.memory_service.recall(
            project_id=self.project_id,
            bank_id=self.bank_id,
            query=query,
            max_results=max_results,
            agent_id=self.agent_id,
        )

    def ask(self, question: str) -> Dict[str, Any]:
        """Perform grounded Q&A against the shared bank."""
        return self.memory_service.ask(
            project_id=self.project_id,
            bank_id=self.bank_id,
            question=question,
            agent_id=self.agent_id,
        )
