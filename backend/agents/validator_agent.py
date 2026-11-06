"""
backend/agents/validator_agent.py
Agent Three: Validator / Compliance.
Cross-checks proposed drafts, PRs, or architecture claims against recalled project memory.
Catches contradictions and enforces institutional alignment.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional
from backend.agents.base_agent import BaseAgent


class ValidatorAgent(BaseAgent):
    """
    Validator agent that inspects technical artifacts or proposed decisions
    against recalled Hindsight memory to catch drift, violations, or direct contradictions.
    """

    def __init__(
        self,
        project_id: str,
        bank_id: str,
        memory_service,
        agent_id: str = "agent-validator",
    ):
        super().__init__(
            agent_id=agent_id,
            role="Validator / QA",
            project_id=project_id,
            bank_id=bank_id,
            memory_service=memory_service,
        )

    def validate(self, draft_text: str, check_topic: Optional[str] = None) -> Dict[str, Any]:
        """
        Validate draft content against recalled project memory.
        Returns contradiction flags, source citations, and detailed analysis.
        """
        search_query = check_topic or draft_text[:120]
        recalled_memories = self.recall(query=search_query, max_results=6)

        context_lines = []
        for idx, m in enumerate(recalled_memories, 1):
            context_lines.append(f"Memory [{idx}] (Author: {m.get('agent_id')}): {m.get('text')}")

        context_str = "\n".join(context_lines) if context_lines else "No memories found on this topic."

        system_prompt = (
            "You are the Strict Architecture & Compliance Validator for an engineering team.\n"
            "Your sole objective is to cross-check the proposed draft against the official project memories provided below.\n\n"
            "CRITICAL VALIDATION RULES:\n"
            "1. ONLY flag 'valid: false' if the draft EXPLICITLY contradicts or violates a recorded decision in the memories.\n"
            "2. If the draft conforms to all memories, or if it introduces details that do not conflict with any recorded memory, you MUST set 'valid: true' and 'contradictions: []'.\n"
            "3. Do not assume or invent conflicts that are not directly established by the recalled memories.\n"
            "4. For each contradiction found, quote the specific text in the draft and cite the contradictory memory.\n\n"
            f"=== OFFICIAL PROJECT MEMORIES ===\n{context_str}\n=================================\n\n"
            "Respond in the following STRICT JSON format only (valid JSON, no markdown outside):\n"
            "{\n"
            '  "valid": true,\n'
            '  "contradictions": [],\n'
            '  "analysis": "Explanation of alignment or violation"\n'
            "}"
        )

        user_prompt = f"Proposed Draft to Validate:\n{draft_text}"
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        raw_output, model_used = self.memory_service.llm.chat(
            messages=messages,
            max_tokens=600,
            temperature=0.0,
        )

        # Parse structured validation result
        valid = True
        contradictions = []
        analysis = raw_output

        try:
            # Strip markdown code blocks if the model wrapped JSON
            clean_json = raw_output.strip()
            if clean_json.startswith("```"):
                clean_json = clean_json.split("\n", 1)[1]
            if clean_json.endswith("```"):
                clean_json = clean_json.rsplit("\n", 1)[0]
            clean_json = clean_json.strip()

            parsed = json.loads(clean_json)
            valid = bool(parsed.get("valid", True))
            raw_contradictions = parsed.get("contradictions", [])
            contradictions = []
            for c in raw_contradictions:
                if isinstance(c, dict):
                    msg = c.get("contradiction") or c.get("reason") or str(c)
                    contradictions.append(str(msg))
                else:
                    contradictions.append(str(c))
            analysis = str(parsed.get("analysis", raw_output))
        except Exception:
            # Fallback heuristic if JSON parsing fails
            lower = raw_output.lower()
            if "contradict" in lower or "violation" in lower or "invalid" in lower:
                valid = False
                contradictions.append("Contradiction identified in validation report.")

        # Log validation check in audit log
        self.memory_service.db.log_audit(
            project_id=self.project_id,
            agent_id=self.agent_id,
            action="validate",
            query_or_text=draft_text[:200],
            result_count=len(contradictions),
        )

        return {
            "valid": valid,
            "contradictions": contradictions,
            "analysis": analysis,
            "citations": recalled_memories,
            "project_id": self.project_id,
            "model_used": model_used,
        }
