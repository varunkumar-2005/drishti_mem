# My Teammate Changed the API; Hindsight Told My Assistant

To test an idea, I staged a small scene. I opened two browser windows side by side and joined both to the same project room—one as "Alice" and one as "Bob". As Bob, I recorded an architecture decision: outbound merchant webhooks must use HMAC-SHA256 signatures with a 300-second timestamp drift window. Within a few seconds, it appeared in Alice’s feed. When Alice asked her assistant to generate a context pack for "write the webhook verification middleware", the new HMAC signing rule was already in the prompt.

That is the problem I built OneContext to solve. Software engineers routinely work with multiple AI assistants (Cursor, Claude, ChatGPT, Copilot), yet each assistant only knows what you have pasted into it. When a teammate changes an API contract or records an architecture decision, your assistant has no idea until code review.

OneContext gives a development team one shared project memory built on [Hindsight](https://github.com/vectorize-io/hindsight), an open-source agent memory engine from Vectorize. Here is how it works, the bugs I hit, and what doesn't work yet.

## How It Fits Together

The core design is simple: one project, one memory bank, every AI assistant. Instead of writing editor plugins for every IDE, OneContext is a small backend that produces bounded text blocks you can paste into any assistant.

* **Hindsight holds the memory.** Each project maps to one Hindsight bank. Decisions, ingested documents, and synced GitHub commits are retained there with metadata (source, author, timestamp). The [Hindsight docs](https://hindsight.vectorize.io/) explain how banks, retain, and semantic recall work together.
* **SQLite holds the bookkeeping.** Team rooms with six-character join codes, an event feed, an audit trail, and supersession links live in SQLite. It stores no embeddings, delegating semantic search to Hindsight.
* **FastAPI pushes updates.** When someone saves a decision or a commit is synced, the backend broadcasts an event over Server-Sent Events. If the stream drops, the client falls back to polling every few seconds.
* **Context packs go out.** For any task, OneContext recalls relevant memories and builds a compact block to paste into Cursor, ChatGPT, or Claude.

[SCREENSHOT: architecture diagram showing members, FastAPI, Hindsight, SQLite, Groq, and the context pack going to an assistant]

## Why Plain Vector Search Wasn't Enough

A plain similarity search over project documentation has three distinct weaknesses for engineering context:

1. **It cannot distinguish active decisions from replaced ones.** If a team picked PostgreSQL in January and migrated financial ledgers to CockroachDB in June, a query about ledger storage retrieves both notes because the keywords match. Because plain similarity scores semantic closeness rather than validity, assistants frequently cite obsolete rules.
2. **Context windows have a cost.** Ingesting dozens of raw specification files wastes tokens on rules unrelated to the task. What assistants require is a bounded list of relevant decisions.
3. **Contradictions go unnoticed.** If one document specifies snake_case parameters while another specifies camelCase, storing both leaves two incompatible truths in the database without warning.

OneContext adds three mechanisms on top of Hindsight: conflict checks at write time, explicit supersession, and length-bounded context compilation.

## Under the Hood

### 1. A Thread-Safe Hindsight Client

FastAPI hands synchronous routes to worker threads. The Hindsight Python client uses `aiohttp` internally, and a client created during server startup broke when invoked from a worker thread. It threw a `RuntimeError` stating that the timeout context manager must run inside a task. The fix was a wrapper creating one client per thread:

```python
# backend/core/hindsight_client.py
import threading
from hindsight_client import Hindsight
from backend.core.config import Settings

class HindsightWrapper:
    def __init__(self, settings: Settings):
        self.base_url = settings.hindsight_base_url
        self.api_key = settings.hindsight_api_key
        self._local = threading.local()

    @property
    def client(self) -> Hindsight:
        if not hasattr(self._local, "client") or self._local.client is None:
            self._local.client = Hindsight(
                base_url=self.base_url,
                api_key=self.api_key,
            )
        return self._local.client
```

All Hindsight calls route through this module, isolating memory operations to one clean interface.

### 2. Conflict Checking at Write Time

Before retaining a decision, OneContext recalls the three most similar existing memories and prompts an LLM at temperature 0.0 to check whether the new text contradicts an earlier decision:

```python
# backend/core/memory_service.py (trimmed)
if check_conflict:
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
        event = self.db.record_event(
            project_id=project_id,
            type="conflict",
            title="Memory Conflict Warning",
            body=f"Contradiction detected: {detected.get('reason', '')}",
            author=agent_id,
        )
        broadcaster.publish_nowait(project_id, event)

memory_id = self.hindsight.retain(
    bank_id=bank_id,
    text=text,
    metadata={**(metadata or {}), "source": source, "author": agent_id},
)
```

The system warns but does not block. In software engineering, exceptions and gradual transitions are normal. Halting writes would obstruct work; instead, a conflict event alerts the room so the team can decide which decision stands.

[SCREENSHOT: conflict warning card showing the old and new decision side by side]

### 3. Corrections That Supersede Obsolete Decisions

When a decision changes, the correction retains the new text with a `supersedes` link and records the pair in SQLite:

```python
# backend/features/corrections.py (trimmed)
retain_res = self.service.retain(
    project_id=project_id,
    bank_id=bank_id,
    text=new_text,
    agent_id=agent_id,
    source="correction",
    check_conflict=False,
    metadata={"supersedes": old_memory_id, "correction_reason": reason},
)
self.db.record_correction(
    project_id=project_id,
    old_memory_id=old_memory_id,
    new_memory_id=retain_res["memory_id"],
    reason=reason,
    old_memory_text=old_memory_text,
)
```

One subtle behavior: Hindsight splits retained sentences into separate atomic facts. Filtering solely by the original memory ID leaves derived fragments in search results, so our filter compares candidate text against the superseded decision text as well.

[SCREENSHOT: a memory card marked Superseded next to the new decision]

### 4. Bounding Context Packs Without Truncating Tasks

A context pack formats recalled facts into a prompt-ready markdown block. An early version sliced the compiled string at `max_chars`, which inadvertently cut off the `[END CONTEXT]` marker and the user's task prompt. The updated logic subtracts the header and footer from the budget upfront and trims excess facts from the bottom:

```python
# backend/api/memory.py (trimmed)
header = (
    f"[PROJECT CONTEXT: {project_name}]\n"
    f"Key decisions and facts relevant to: {payload.task}\n"
)
footer = f"[END CONTEXT]\n\n{payload.task}"
budget = payload.max_chars - len(header) - len(footer)

selected_lines = []
used_chars = 0
for line, mem in formatted_facts:
    if used_chars + len(line) > budget:
        break  # Truncate facts from bottom, never wrapper or task
    selected_lines.append(line)
    used_chars += len(line)

final_pack = header + "".join(selected_lines) + footer
```

When targeting Cursor, the generator outputs comment headers (`# Cursor Project Rules`). Retrieval logic stays uniform across all targets.

## What It Looks Like in Use

Setting up a shared session takes three steps in the web interface:

* **Joining a room:** One developer creates a room and receives a six-character join code. Teammates enter the code to connect to the same Hindsight bank. The sidebar displays active team presence.
* **Live activity feed:** When Bob saved the webhook rule, it appeared in Alice’s feed within a few seconds. If a GitHub repo is connected, commits are polled every 45 seconds and displayed alongside manual decisions.
* **Catch me up summary:** When returning from away, a developer clicks Catch Me Up. The LLM summarizes events since their last session at temperature 0.0, instructed to preserve names, numbers, and file paths exactly as recorded.

[SCREENSHOT: two windows side by side in the same room]
[SCREENSHOT: the Catch me up summary]

### Before and After: Real Output Comparison

To measure grounding impact, I ran `demo_context_pack.py` with an architecture specification and posed the same query:

> **Question:** *"What is our policy on public API protocols and database pooling?"*

**Without a Context Pack (Ungrounded):**

```
I’m sorry—I don’t have access to your organization’s internal documentation,
so I can’t provide the specific policy that your team has defined for public
API protocols or database-connection pooling.

However, I can share some common best-practice guidelines that many companies
adopt in these areas:
- Transport Layer: HTTPS only (TLS 1.2+; prefer TLS 1.3).
- Authentication: OAuth 2.0 (Authorization Code, Client Credentials, or JWT).
- Rate Limiting: Per-client quotas with 429 Too Many Requests when exceeded.
```

**With Context Pack (Grounded in OneContext Project Memory):**

```
Public-API protocol policy:
- Only RESTful HTTP interfaces are allowed for any external-facing
  microservice. Those endpoints must be described with an OpenAPI v3.1 schema.
- GraphQL and gRPC are not permitted on public internet gateways. They
  may be used internally, but cannot be exposed publicly.

Database-pooling policy:
- The connection pool for each pod is limited to a maximum of 20 database
  connections. This limit is enforced to prevent PostgreSQL connection saturation.
```

The grounded model cited exact repository standards, identified prohibited gateway protocols, and provided the precise connection limit needed for service configuration.

[SCREENSHOT: the Context Pack page, with the generated pack and its sources]

## What Doesn't Work Yet

1. **LLM-based conflict checks can be wrong.** The conflict detector and validator agent rely on model inference. They can miss nuanced contradictions or misinterpret harmless additions.
2. **Corrections rely on heuristic text matching.** Because Hindsight decomposes text into multiple facts, an older fact phrased with alternate terminology can slip past the filter.
3. **Indexing delay.** Hindsight indexes retained memories asynchronously. While SSE notifications arrive within a few seconds, new decisions need a brief indexing window before appearing in recall.
4. **No granular permissions.** Anyone with the room join code has full read and write access to the memory bank.
5. **Polling-based GitHub sync.** Commits are pulled by a worker polling every 45 seconds rather than triggered by immediate webhooks.
6. **Pasted packs rather than direct editor integration.** OneContext outputs markdown blocks to copy and paste; it does not yet integrate directly into IDE extension runtimes.

## Lessons Learned

* **Invalidation matters more than retrieval depth.** Finding semantically related documents is relatively easy; pruning obsolete or superseded facts is where agent memory systems succeed or fail.
* **Know your memory engine's parsing model.** Hindsight decomposes raw sentences into atomic facts. That enhances recall precision, but requires supersession logic to account for decomposed fragments.
* **A portable text format beats editor plugins for adoption.** Generating bounded markdown blocks allows any assistant (Cursor, Claude, ChatGPT) to consume memory without maintaining multiple extension codebases.
* **Warn, don't block.** Hard write blocks frustrate developers during rapid iteration. Showing side-by-side contradictions lets humans make informed architectural choices.
* **Keep client initialization thread-isolated.** Wrapping client creation in thread-local storage avoided concurrency crashes across worker threads and kept API route logic clean.

## Conclusion

An AI assistant is only as effective as the context provided to it. By establishing a shared memory bank in [Hindsight](https://github.com/vectorize-io/hindsight), OneContext guarantees that when one developer makes an architectural decision, every teammate's assistant can work from the same reality. To explore how continuous state transforms multi-agent workflows, review Vectorize's guide on [agent memory](https://vectorize.io/what-is-agent-memory).

Thanks to Code.in for supporting open developer collaboration tools.
