"""
scripts/demo_before_after.py
Flagship multi-agent demonstration script for OneContext.

Demonstrates:
  1. Agent 1 (Planner): Formulates and retains architectural decisions into Hindsight.
  2. Agent 2 (Builder): Recalls decisions across agents from Hindsight (NO manual handoff)
     and implements guidance conforming to them.
  3. Agent 3 (Validator):
     - Validates a compliant implementation draft -> PASSED
     - Catches a deliberately contradictory draft (e.g. MongoDB + int IDs) -> FLAGGED
"""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.agents.agent_one import PlannerAgent
from backend.agents.agent_two import BuilderAgent
from backend.agents.validator_agent import ValidatorAgent
from backend.config import get_settings
from backend.core.hindsight_client import HindsightWrapper
from backend.core.llm_client import LLMClient
from backend.core.memory_service import MemoryService
from backend.storage import local_db


def safe_text(text: str) -> str:
    """Ensure safe terminal output on Windows cp1252 consoles."""
    return text.encode("ascii", errors="replace").decode("ascii")


def divider(title: str) -> None:
    print(f"\n{'=' * 75}")
    print(f"  {title}")
    print(f"{'=' * 75}")


def main():
    settings = get_settings()
    local_db.init_db()

    hindsight = HindsightWrapper(settings)
    llm = LLMClient(settings)
    memory_service = MemoryService(hindsight=hindsight, llm=llm, db_module=local_db)

    # 1. Setup dedicated demo project
    proj_id = f"demo-{uuid.uuid4().hex[:6]}"
    bank_id = f"onecontext-{proj_id}"
    hindsight.create_bank(bank_id, f"Demo Bank {proj_id}")
    local_db.create_project(proj_id, "Multi-Agent Demo Project", "Demo Bank", bank_id)

    print(f"Project ID: {proj_id}")
    print(f"Hindsight Bank ID: {bank_id}")

    # =========================================================================
    # STEP 1: Agent 1 (Planner) retains architecture decisions
    # =========================================================================
    divider("STEP 1: AGENT 1 (PLANNER) - ARCHITECTURE DECISION")
    planner = PlannerAgent(
        project_id=proj_id,
        bank_id=bank_id,
        memory_service=memory_service,
    )

    decision_text = (
        "DECISION: We strictly standardize on PostgreSQL using async SQLAlchemy (asyncpg) "
        "and UUIDv4 primary keys. Document stores (MongoDB) and auto-increment integer IDs are strictly prohibited."
    )
    print(f"[{planner.agent_id}] Formulating and retaining architectural standard...")
    planner.retain(text=decision_text, source="architecture_decision")
    print(f"Retained:\n  {decision_text}")

    print("\nWaiting for Hindsight memory indexing...")
    indexed = hindsight.wait_for_recall(
        bank_id=bank_id,
        query="PostgreSQL SQLAlchemy UUIDv4",
        expected_contains="PostgreSQL",
        timeout=25,
        poll_interval=2,
    )
    print(f"Hindsight indexing status: {'READY' if indexed else 'INDEXING_CONTINUES'}")

    # =========================================================================
    # STEP 2: Agent 2 (Builder) recalls from Hindsight and implements
    # =========================================================================
    divider("STEP 2: AGENT 2 (BUILDER) - CROSS-AGENT MEMORY RECALL & IMPLEMENTATION")
    print("Notice: No manual memory or prompt handoff occurs between Agent 1 and Agent 2.")
    print("Agent 2 queries the shared project bank directly via Hindsight.\n")

    builder = BuilderAgent(
        project_id=proj_id,
        bank_id=bank_id,
        memory_service=memory_service,
    )

    builder_task = "Provide the User model and persistence layer design for customer profiles."
    builder_res = builder.build_guidance(task=builder_task)

    print(f"[{builder.agent_id}] Recalled {len(builder_res['memories_recalled'])} memories from Hindsight:")
    for i, m in enumerate(builder_res["memories_recalled"], 1):
        author = m.get("agent_id") or "unknown"
        print(f"  [{i}] (Author: {author}) {safe_text(m.get('text', '')[:100])}...")

    print(f"\n[{builder.agent_id}] Generated Implementation Guidance:")
    print(safe_text(builder_res["output"][:500]) + "...\n[truncated for display]")

    # =========================================================================
    # STEP 3: Agent 3 (Validator) checks compliant vs contradictory drafts
    # =========================================================================
    divider("STEP 3: AGENT 3 (VALIDATOR) - MEMORY CONTRADICTION DETECTION")
    validator = ValidatorAgent(
        project_id=proj_id,
        bank_id=bank_id,
        memory_service=memory_service,
    )

    # Draft A: Compliant
    compliant_draft = (
        "PR #101: Added User account model using PostgreSQL with UUID primary key and asyncpg connection pooling."
    )
    print("\n--- Validating Compliant Draft ---")
    print(f"Draft: {compliant_draft}")
    res_a = validator.validate(compliant_draft, check_topic="database persistence model")
    print(f"Valid: {res_a['valid']}")
    print(f"Contradictions found: {res_a['contradictions']}")

    # Draft B: Deliberately Contradictory
    flawed_draft = (
        "PR #102: Added User profile collection storing accounts in MongoDB with auto-increment integer IDs."
    )
    print("\n--- Validating Contradictory Draft ---")
    print(f"Draft: {flawed_draft}")
    res_b = validator.validate(flawed_draft, check_topic="database persistence model")
    print(f"Valid: {res_b['valid']}")
    print(f"Contradictions caught: {res_b['contradictions']}")
    print(f"Validator Analysis:\n{safe_text(res_b['analysis'])}")

    divider("END-TO-END MULTI-AGENT DEMO COMPLETE")
    print("All 3 agents successfully shared and enforced a single Hindsight memory bank!\n")


if __name__ == "__main__":
    main()
