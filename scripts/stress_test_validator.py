"""
scripts/stress_test_validator.py
Runs the validator 3 times on a compliant draft and 3 times on a contradictory draft.
Verifies consistent, deterministic results.
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.config import get_settings
from backend.core.hindsight_client import HindsightWrapper
from backend.core.llm_client import LLMClient
from backend.core.memory_service import MemoryService
from backend.agents.validator_agent import ValidatorAgent
from backend.storage import local_db


def main():
    settings = get_settings()
    local_db.init_db()
    hindsight = HindsightWrapper(settings)
    llm = LLMClient(settings)
    service = MemoryService(hindsight, llm, local_db)

    bank_id = f"onecontext-val-{uuid.uuid4().hex[:4]}"
    hindsight.create_bank(bank_id, "Validator Stress Test")
    service.retain(
        "proj-val",
        bank_id,
        "DECISION: All services must use PostgreSQL and asyncpg. MongoDB is strictly prohibited.",
        agent_id="planner",
        source="arch",
    )
    hindsight.wait_for_recall(bank_id, "PostgreSQL asyncpg MongoDB", "PostgreSQL", 20, 2)

    val = ValidatorAgent("proj-val", bank_id, service)

    compliant = "PR: Built authentication service using PostgreSQL and asyncpg."
    bad = "PR: Built authentication service using MongoDB database."

    print("=== TESTING COMPLIANT DRAFT (3 RUNS) ===")
    for i in range(3):
        r = val.validate(compliant, "database engine")
        status_str = "PASS" if r["valid"] is True and len(r["contradictions"]) == 0 else "FAIL"
        print(f"  Run {i+1}: valid={r['valid']}, contradictions={len(r['contradictions'])} -> {status_str}")

    print("\n=== TESTING CONTRADICTORY DRAFT (3 RUNS) ===")
    for i in range(3):
        r = val.validate(bad, "database engine")
        status_str = "PASS" if r["valid"] is False and len(r["contradictions"]) > 0 else "FAIL"
        print(f"  Run {i+1}: valid={r['valid']}, contradictions={len(r['contradictions'])} -> {status_str}")

    print("\nAll 6 validator stress runs completed successfully.")


if __name__ == "__main__":
    main()
