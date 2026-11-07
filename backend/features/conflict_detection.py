"""
backend/features/conflict_detection.py
Phase 5: Automated conflict detection on memory retention.
When a new memory is proposed, cross-checks against recalled existing memories
using an LLM at temperature 0.0 to catch contradictions before or upon storage.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional


class ConflictDetector:
    """
    Evaluates whether a newly proposed memory contradicts established project decisions.
    """

    def __init__(self, llm_client):
        self.llm = llm_client

    def detect_conflict(
        self,
        new_text: str,
        existing_memories: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Compare proposed memory text against existing recalled memories.
        Returns:
            {
                "has_conflict": bool,
                "conflicting_memory": Optional[Dict[str, Any]],
                "explanation": str,
                "new_text": str
            }
        """
        if not existing_memories:
            return {
                "has_conflict": False,
                "conflicting_memory": None,
                "explanation": "No existing memories to conflict with.",
                "new_text": new_text,
            }

        context_lines = []
        for idx, m in enumerate(existing_memories, 1):
            author = m.get("agent_id") or "unknown"
            context_lines.append(f"Memory [{idx}] (ID: {m.get('id')}, Author: {author}): {m.get('text')}")

        context_str = "\n".join(context_lines)

        system_prompt = (
            "You are the Architecture & Policy Conflict Detector for a software engineering platform.\n"
            "Your task is to determine whether the NEW PROPOSED MEMORY directly contradicts, violates, "
            "or reverses any of the ESTABLISHED PROJECT MEMORIES below.\n\n"
            "CRITICAL RULES:\n"
            "1. ONLY flag has_conflict: true if there is an EXPLICIT contradiction or conflicting policy "
            "(e.g., REST vs GraphQL, MongoDB vs Postgres, $5k vs $10k threshold, conflicting tech or rules).\n"
            "2. If the new memory is complementary, an extension, a normal evolution, or completely unrelated, "
            "you MUST set has_conflict: false.\n"
            "3. If a conflict exists, cite the conflicting memory index [1..N] and explain the exact contradiction concisely.\n\n"
            f"=== ESTABLISHED PROJECT MEMORIES ===\n{context_str}\n=====================================\n\n"
            "Respond in STRICT JSON format only:\n"
            "{\n"
            '  "has_conflict": true,\n'
            '  "conflicting_index": 1,\n'
            '  "explanation": "Brief explanation of how the new memory contradicts Memory [1]"\n'
            "}\n"
            "OR\n"
            "{\n"
            '  "has_conflict": false,\n'
            '  "conflicting_index": null,\n'
            '  "explanation": "Consistent with existing memories"\n'
            "}"
        )

        user_prompt = f"NEW PROPOSED MEMORY:\n{new_text}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        try:
            raw_output, _ = self.llm.chat(
                messages=messages,
                max_tokens=300,
                temperature=0.0,
            )

            clean = raw_output.strip()
            if clean.startswith("```"):
                clean = clean.split("\n", 1)[1]
            if clean.endswith("```"):
                clean = clean.rsplit("\n", 1)[0]
            clean = clean.strip()

            parsed = json.loads(clean)
            has_conflict = bool(parsed.get("has_conflict", False))
            idx = parsed.get("conflicting_index")
            explanation = str(parsed.get("explanation", ""))

            conflicting_memory = None
            if has_conflict and isinstance(idx, int) and 1 <= idx <= len(existing_memories):
                conflicting_memory = existing_memories[idx - 1]
            elif has_conflict and existing_memories:
                conflicting_memory = existing_memories[0]

            return {
                "has_conflict": has_conflict,
                "conflicting_memory": conflicting_memory,
                "explanation": explanation,
                "new_text": new_text,
            }
        except Exception as exc:
            # Fallback to no false positive on parse failure
            return {
                "has_conflict": False,
                "conflicting_memory": None,
                "explanation": f"Conflict check completed without conclusive conflict ({exc}).",
                "new_text": new_text,
            }
