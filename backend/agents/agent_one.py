"""
backend/agents/agent_one.py
Agent One: Planner / Architect.
Formulates project architectural decisions and retains them directly into the shared Hindsight bank.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List
from backend.agents.base_agent import BaseAgent


class PlannerAgent(BaseAgent):
    """
    Planner agent responsible for high-level technical decisions, conventions, and architecture.
    Persists key decisions into Hindsight so other agents can discover and follow them.
    """

    def __init__(
        self,
        project_id: str,
        bank_id: str,
        memory_service,
        agent_id: str = "agent-planner",
    ):
        super().__init__(
            agent_id=agent_id,
            role="Planner / Architect",
            project_id=project_id,
            bank_id=bank_id,
            memory_service=memory_service,
        )

    def plan_and_retain(self, task: str, context: str = "") -> Dict[str, Any]:
        """
        Formulate an architectural plan or decision for a task and commit key decisions into memory.
        """
        # First recall any existing context on this topic
        existing_memories = self.recall(query=task, max_results=3)
        context_notes = "\n".join([f"- {m.get('text')}" for m in existing_memories])

        system_prompt = (
            "You are the Lead Software Architect (Planner Agent) for this project.\n"
            "Given a requirement or architecture question, formulate a clear, authoritative decision.\n"
            "Conclude with 1 to 3 explicit decision statements in bullet format labeled 'DECISION:' that must be stored in project memory.\n"
            f"Existing Project Context:\n{context_notes or 'None'}"
        )

        user_prompt = f"Architecture Task: {task}\nAdditional Context: {context}"
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        response, model_used = self.memory_service.llm.chat(messages=messages, max_tokens=600)

        # Extract explicit DECISION bullet points to retain
        decisions_to_retain = []
        for line in response.splitlines():
            clean = line.strip()
            if "DECISION:" in clean:
                decision_text = clean.split("DECISION:", 1)[1].strip()
                if decision_text:
                    decisions_to_retain.append(decision_text)

        # If no explicit markers found, retain the first meaningful summary paragraph
        if not decisions_to_retain:
            paragraphs = [p.strip() for p in response.split("\n\n") if p.strip()]
            if paragraphs:
                decisions_to_retain.append(paragraphs[0])

        retained_ids = []
        for d in decisions_to_retain:
            ret = self.retain(text=d, source="architecture_decision")
            retained_ids.append(d)

        return {
            "output": response,
            "decisions_retained": decisions_to_retain,
            "memories_recalled": existing_memories,
            "model_used": model_used,
        }
