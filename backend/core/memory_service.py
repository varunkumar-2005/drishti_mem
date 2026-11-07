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
from backend.core.broadcaster import broadcaster
from backend.features.attribution import format_source_attribution
from backend.features.conflict_detection import ConflictDetector
from backend.features.corrections import CorrectionsManager
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
        self.conflict_detector = ConflictDetector(llm)
        self.corrections_manager = CorrectionsManager(self, db_module)

    def retain(
        self,
        project_id: str,
        bank_id: str,
        text: str,
        agent_id: str = "user",
        source: str = "note",
        check_conflict: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Retain a memory, optionally checking for conflicts, attaching metadata and recording to audit log."""
        now_iso = datetime.now(timezone.utc).isoformat()
        full_metadata = {
            "project_id": project_id,
            "agent_id": agent_id,
            "source": source,
            "timestamp": now_iso,
        }
        if metadata:
            full_metadata.update(metadata)

        conflict_info = None
        if check_conflict:
            # Check if this new memory contradicts existing memories
            existing = self.recall(
                project_id=project_id,
                bank_id=bank_id,
                query=text,
                max_results=3,
                include_superseded=False,
            )
            detected = self.conflict_detector.detect_conflict(text, existing)
            if detected.get("has_conflict"):
                conflict_info = detected
                conflicting_mem = detected.get("conflicting_memory") or {}
                conflicting_text = conflicting_mem.get("text", "")[:80]
                self.db.log_audit(
                    project_id=project_id,
                    agent_id=agent_id,
                    action="conflict_detected",
                    query_or_text=f"New: {text[:80]} vs Old: {conflicting_text}",
                    result_count=1,
                    timestamp=now_iso,
                )

        memory_id = self.hindsight.retain(
            bank_id=bank_id,
            text=text,
            metadata=full_metadata,
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

        # Record events for live room feed
        if conflict_info:
            conflicting_mem = conflict_info.get("conflicting_memory") or {}
            c_text = conflicting_mem.get("text", "")
            c_event = self.db.record_event(
                project_id=project_id,
                type="conflict",
                title="Memory Conflict Warning",
                body=f"Statement '{text}' conflicts with prior decision: '{c_text}'",
                author=agent_id,
            )
            if c_event:
                broadcaster.publish_nowait(project_id, c_event)

        event_type = "decision" if source in ("decision", "manual_capture", "note", "user", "agent") else "document"
        e_title = text[:80] + ("..." if len(text) > 80 else "")
        d_event = self.db.record_event(
            project_id=project_id,
            type=event_type,
            title=e_title,
            body=text,
            author=agent_id,
        )
        if d_event:
            broadcaster.publish_nowait(project_id, d_event)

        res = {
            "memory_id": memory_id,
            "project_id": project_id,
            "agent_id": agent_id,
            "source": source,
            "timestamp": now_iso,
            "conflict": conflict_info,
        }
        if metadata and "supersedes" in metadata:
            res["supersedes"] = metadata["supersedes"]
        return res

    def correct(
        self,
        project_id: str,
        bank_id: str,
        old_memory_id: str,
        new_text: str,
        agent_id: str = "user",
        reason: str = "",
        old_memory_text: str = "",
    ) -> Dict[str, Any]:
        """Create a corrective memory that supersedes an older one and its derived facts."""
        return self.corrections_manager.correct(
            project_id=project_id,
            bank_id=bank_id,
            old_memory_id=old_memory_id,
            new_text=new_text,
            agent_id=agent_id,
            reason=reason,
            old_memory_text=old_memory_text,
        )

    def recall(
        self,
        project_id: str,
        bank_id: str,
        query: str,
        max_results: int = 5,
        agent_id: str = "user",
        include_superseded: bool = True,
    ) -> List[Dict[str, Any]]:
        """Retrieve memories and format them with attribution metadata, preferring active non-superseded entries."""
        raw_items = self.hindsight.recall(
            bank_id=bank_id,
            query=query,
            max_results=max_results,
        )

        superseded_ids = set()
        superseded_texts = []
        if hasattr(self.db, "get_superseded_info"):
            info = self.db.get_superseded_info(project_id)
            superseded_ids = info.get("ids", set())
            superseded_texts = info.get("texts", [])
        elif hasattr(self.db, "get_superseded_memory_ids"):
            superseded_ids = self.db.get_superseded_memory_ids(project_id)

        formatted_items: List[Dict[str, Any]] = []
        seen_texts = set()

        import re

        stopwords = {
            "the", "a", "an", "is", "are", "and", "or", "to", "for", "in", "on", "of", "with",
            "all", "our", "we", "project", "standard", "decision", "must", "strictly", "requires",
            "when", "official", "architectural", "using", "use", "per", "from", "by", "at",
        }

        for item in raw_items:
            raw_text = item.get("text", "").strip()
            # Normalize text for deduplication comparison
            norm = " ".join(raw_text.lower().split())
            if norm in seen_texts:
                continue
            seen_texts.add(norm)

            meta = item.get("metadata") or {}
            mem_id = item.get("id") or meta.get("id") or str(uuid.uuid4())[:8]

            # 1. Exact ID check
            is_superseded = mem_id in superseded_ids or bool(meta.get("is_superseded"))

            # 2. Multi-fact derivation check: exclude all facts extracted from the superseded retain
            if not is_superseded and not meta.get("supersedes") and superseded_texts:
                norm_clean = re.sub(r"[^a-zA-Z0-9\s]", " ", norm.lower())
                norm_tokens = set(norm_clean.split()) - stopwords
                if norm_tokens:
                    for old_text in superseded_texts:
                        old_clean = re.sub(r"[^a-zA-Z0-9\s]", " ", old_text.lower())
                        old_tokens = set(old_clean.split()) - stopwords
                        if not old_tokens:
                            continue
                        common = norm_tokens & old_tokens
                        overlap = len(common) / min(len(norm_tokens), len(old_tokens))
                        if len(common) >= 3 or overlap >= 0.40 or norm_clean in old_clean or old_clean in norm_clean:
                            is_superseded = True
                            break

            if not include_superseded and is_superseded:
                continue

            item_dict = {
                "id": mem_id,
                "text": raw_text,
                "type": item.get("type"),
                "source": meta.get("source"),
                "agent_id": meta.get("agent_id"),
                "timestamp": meta.get("timestamp"),
                "score": item.get("score"),
                "metadata": meta,
                "supersedes": meta.get("supersedes"),
                "is_superseded": is_superseded,
            }
            formatted_items.append(format_source_attribution(item_dict))

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
            include_superseded=False,
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
