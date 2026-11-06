"""
backend/agents/agent_two.py
Agent Two: Builder / Coder.
Recalls technical decisions from the shared Hindsight bank and produces implementation code/guidance.
Does NOT receive manual handoffs from Agent 1 — discovers decisions strictly via memory recall.
"""

from __future__ import annotations

from typing import Any, Dict, List
from backend.agents.base_agent import BaseAgent


class BuilderAgent(BaseAgent):
    """
    Builder agent that implements features according to the team's stored decisions.
    Fetches required conventions and rules strictly through Hindsight recall.
    """

    def __init__(
        self,
        project_id: str,
        bank_id: str,
        memory_service,
        agent_id: str = "agent-builder",
    ):
        super().__init__(
            agent_id=agent_id,
            role="Builder / Coder",
            project_id=project_id,
            bank_id=bank_id,
            memory_service=memory_service,
        )

    def build_guidance(self, task: str, context: str = "") -> Dict[str, Any]:
        """
        Produce implementation guidance and code snippets, strictly adhering to recalled project memory.
        """
        # Recall decisions relevant to the coding task
        recalled_memories = self.recall(query=task, max_results=5)

        context_blocks = []
        for idx, m in enumerate(recalled_memories, 1):
            author = m.get("agent_id") or "project"
            src = m.get("source") or "general"
            context_blocks.append(f"[{idx}] (Author: {author}, Source: {src}): {m.get('text')}")

        context_str = "\n".join(context_blocks) if context_blocks else "No relevant project memory found."

        system_prompt = (
            "You are the Senior Implementation Engineer (Builder Agent).\n"
            "Your job is to provide concrete code and implementation instructions for the requested task.\n"
            "CRITICAL: You MUST strictly conform to the project decisions and conventions recalled from memory below.\n"
            "Explicitly cite which recalled decision guided each implementation choice.\n\n"
            f"=== RECALLED PROJECT DECISIONS (via Hindsight) ===\n{context_str}\n================================================"
        )

        user_prompt = f"Implementation Task: {task}\nAdditional Details: {context}"
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        response, model_used = self.memory_service.llm.chat(messages=messages, max_tokens=700)

        # Retain implementation note
        summary_note = f"Builder implemented guidance for '{task}' adhering to {len(recalled_memories)} recalled decisions."
        self.retain(text=summary_note, source="implementation_note")

        return {
            "output": response,
            "memories_recalled": recalled_memories,
            "decisions_retained": [summary_note],
            "model_used": model_used,
        }
