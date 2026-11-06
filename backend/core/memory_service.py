"""
backend/core/memory_service.py
Core orchestration service for OneContext.
Combines Hindsight (long-term memory) and Groq (LLM reasoning).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from backend.core.hindsight_client import HindsightWrapper
from backend.core.llm_client import LLMClient
from backend.storage import local_db


class MemoryService:
    """Orchestrates memory retention, recall, and grounded RAG answering."""

    def __init__(
        self,
        hindsight: HindsightWrapper,
        llm: LLMClient,
        db_module=local_db,
    ):
        self.hindsight = hindsight
        self.llm = llm
        self.db = db_module

    def retain(
        self,
        project_id: str,
        bank_id: str,
        text: str,
        agent_id: str = "user",
        source: str = "note",
    ) -> Dict[str, Any]:
        """Retain a memory, attaching metadata and recording to the audit log."""
        now_iso = datetime.now(timezone.utc).isoformat()
        metadata = {
            "project_id": project_id,
            "agent_id": agent_id,
            "source": source,
            "timestamp": now_iso,
        }

        memory_id = self.hindsight.retain(
            bank_id=bank_id,
            text=text,
            metadata=metadata,
        )

        # Record in local SQLite audit trail
        self.db.log_audit(
            project_id=project_id,
            agent_id=agent_id,
            action="retain",
            query_or_text=text,
            result_count=1,
            timestamp=now_iso,
        )

        return {
            "memory_id": memory_id,
            "project_id": project_id,
            "agent_id": agent_id,
            "source": source,
            "timestamp": now_iso,
        }

    def recall(
        self,
        project_id: str,
        bank_id: str,
        query: str,
        max_results: int = 5,
        agent_id: str = "user",
    ) -> List[Dict[str, Any]]:
        """Retrieve memories and format them with attribution metadata."""
        raw_items = self.hindsight.recall(
            bank_id=bank_id,
            query=query,
            max_results=max_results,
        )

        formatted_items: List[Dict[str, Any]] = []
        for item in raw_items:
            meta = item.get("metadata") or {}
            formatted_items.append(
                {
                    "id": item.get("id") or str(uuid.uuid4())[:8],
                    "text": item.get("text", ""),
                    "type": item.get("type"),
                    "source": meta.get("source"),
                    "agent_id": meta.get("agent_id"),
                    "timestamp": meta.get("timestamp"),
                    "score": item.get("score"),
                    "metadata": meta,
                }
            )

        # Log search in audit log
        self.db.log_audit(
            project_id=project_id,
            agent_id=agent_id,
            action="recall",
            query_or_text=query,
            result_count=len(formatted_items),
        )

        return formatted_items

    def ask(
        self,
        project_id: str,
        bank_id: str,
        question: str,
        agent_id: str = "user",
    ) -> Dict[str, Any]:
        """Answer a question using recalled project memories (grounded RAG)."""
        sources = self.recall(
            project_id=project_id,
            bank_id=bank_id,
            query=question,
            max_results=5,
            agent_id=agent_id,
        )

        # Build prompt with context
        context_blocks = []
        for idx, src in enumerate(sources, 1):
            agent = src.get("agent_id") or "unknown"
            source_type = src.get("source") or "general"
            context_blocks.append(
                f"[{idx}] (Source: {source_type}, Author: {agent})\n{src.get('text')}"
            )

        context_str = "\n\n".join(context_blocks) if context_blocks else "No relevant memories found."

        system_prompt = (
            "You are a helpful software engineering assistant with access to the team's long-term project memory.\n"
            "Answer the question directly, accurately, and cite relevant details from the provided project memories.\n"
            "If the memories do not contain the answer, state what you know or note that it wasn't recorded.\n\n"
            f"=== PROJECT MEMORY CONTEXT ===\n{context_str}\n=============================="
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question},
        ]

        answer, model_used = self.llm.chat(messages=messages, max_tokens=512)

        # Audit log
        self.db.log_audit(
            project_id=project_id,
            agent_id=agent_id,
            action="ask",
            query_or_text=question,
            result_count=len(sources),
        )

        return {
            "question": question,
            "answer": answer,
            "sources": sources,
            "project_id": project_id,
            "model_used": model_used,
        }

    def ask_without_memory(
        self,
        question: str,
        agent_id: str = "user",
    ) -> Dict[str, Any]:
        """Answer a question WITHOUT any recalled memories (for Before/After comparison)."""
        system_prompt = (
            "You are a helpful software engineering assistant answering a technical question without access "
            "to any internal team documentation or project memory."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question},
        ]

        answer, model_used = self.llm.chat(messages=messages, max_tokens=512)

        return {
            "question": question,
            "answer": answer,
            "sources": [],
            "project_id": None,
            "model_used": model_used,
        }
