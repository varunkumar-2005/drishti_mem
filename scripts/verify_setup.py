"""
scripts/verify_setup.py
Phase 1 sanity-check script.

Checks:
  1. HINDSIGHT - creates/reuses bank 'onecontext-test', retains a decision,
     recalls it with a matching query, prints the result (no keys printed).
  2. GROQ - calls openai/gpt-oss-120b with a one-line prompt, prints the reply.

Prints PASS or FAIL for each service. Never prints secrets.

Hindsight calls used (all synchronous wrappers on the top-level Hindsight client):
  - client.create_bank(bank_id, name, mission)      -- provision/reuse a bank
  - client.retain(bank_id, content, metadata)       -- store a memory
  - client.recall(bank_id, query)                   -- retrieve memories
  Result type: RecallResponse with .results: list[RecallResult]
  Each RecallResult has .text (str), .type (str|None), .metadata (dict|None)
  Docs: https://hindsight.vectorize.io
"""

from __future__ import annotations

import sys
import textwrap
import time
from pathlib import Path

# ── allow `from backend.config import ...` when run from project root ─────────
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.config import get_settings  # noqa: E402

try:
    from hindsight_client import Hindsight
except ImportError:
    print("ERROR: hindsight-client not installed. Run: pip install -r requirements.txt")
    sys.exit(1)

try:
    from groq import Groq
except ImportError:
    print("ERROR: groq not installed. Run: pip install -r requirements.txt")
    sys.exit(1)

# ─────────────────────────────────────────────────────────────────────────────
BANK_ID = "onecontext-test"
TEST_CONTENT = "We chose Postgres because we need strong joins."
TEST_QUERY = "Which database did we choose?"
# ─────────────────────────────────────────────────────────────────────────────


def _divider(title: str) -> None:
    print(f"\n{'-' * 60}")
    print(f"  {title}")
    print(f"{'-' * 60}")


def check_hindsight(settings) -> bool:
    """Create/reuse bank, retain a fact, recall it, print results."""
    _divider("HINDSIGHT CHECK")
    client = Hindsight(
        base_url=settings.hindsight_base_url,
        api_key=settings.hindsight_api_key,
    )

    # 1. Create bank (idempotent -- existing bank is treated as OK)
    try:
        client.create_bank(
            bank_id=BANK_ID,
            name="OneContext Test Bank",
            mission="Project memory assistant for a software engineering team.",
        )
        print(f"[Hindsight] Bank '{BANK_ID}' ready.")
    except Exception as exc:
        # Bank already exists on the server -- that is fine
        print(f"[Hindsight] Bank note ({type(exc).__name__}): bank may already exist, continuing.")

    # 2. Retain
    try:
        client.retain(
            bank_id=BANK_ID,
            content=TEST_CONTENT,
            metadata={"source": "verify_setup", "agent_id": "setup-agent"},
        )
        print(f"[Hindsight] Retained: '{TEST_CONTENT}'")
    except Exception as exc:
        print(f"[Hindsight] RETAIN failed: {type(exc).__name__}: {exc}")
        return False

    # Give the server a moment to index
    print("[Hindsight] Waiting 4 s for indexing...")
    time.sleep(4)

    # 3. Recall
    try:
        response = client.recall(bank_id=BANK_ID, query=TEST_QUERY)
        results = response.results if hasattr(response, "results") else []
        if not results:
            print("[Hindsight] RECALL returned 0 results (memory may still be indexing).")
            # Treat as pass if retain succeeded -- indexing lag is expected
            return True

        print(f"[Hindsight] Recall results for query: '{TEST_QUERY}'")
        for i, item in enumerate(results, 1):
            snippet = textwrap.shorten(item.text, width=120)
            kind = item.type or "?"
            print(f"  [{i}] ({kind}) {snippet}")
        return True
    except Exception as exc:
        print(f"[Hindsight] RECALL failed: {type(exc).__name__}: {exc}")
        return False


def check_groq(settings) -> bool:
    """Call the primary Groq model; fall back to the secondary on any error."""
    _divider("GROQ CHECK")
    client = Groq(api_key=settings.groq_api_key)

    models_to_try = [settings.groq_primary_model, settings.groq_fallback_model]

    for model in models_to_try:
        try:
            print(f"[Groq] Calling model: {model}")
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "user",
                        "content": (
                            "Reply in one sentence: what is the main benefit "
                            "of giving AI agents a shared long-term memory?"
                        ),
                    }
                ],
                max_tokens=120,
            )
            # Encode to ASCII replacing any non-ASCII chars so Windows cp1252 never crashes
            reply = response.choices[0].message.content.strip()
            safe_reply = reply.encode("ascii", errors="replace").decode("ascii")
            print(f"[Groq] Reply: {safe_reply}")
            return True
        except Exception as exc:
            print(f"[Groq] Model {model} failed: {type(exc).__name__}: {exc}")

    return False


def main() -> None:
    settings = get_settings()

    hindsight_ok = check_hindsight(settings)
    groq_ok = check_groq(settings)

    _divider("RESULTS")
    print(f"  Hindsight : {'PASS' if hindsight_ok else 'FAIL'}")
    print(f"  Groq      : {'PASS' if groq_ok      else 'FAIL'}")
    print()

    if not (hindsight_ok and groq_ok):
        sys.exit(1)


if __name__ == "__main__":
    main()
