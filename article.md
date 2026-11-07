# My Teammate Changed the API; Hindsight Told My Assistant

Last Tuesday, our backend lead updated our payment webhook retry contract, bumping our exponential backoff ceiling from five seconds to sixty seconds and mandating timestamp anti-replay validation. Ten minutes later, another engineer on our team opened Cursor to scaffold downstream webhook consumers, and their assistant generated code with five-second timeouts and no replay checks. 

In almost every engineering team using modern generative tools, this scenario plays out daily: developers work with isolated AI assistants—Cursor, Claude Code, ChatGPT, Copilot—each trapped inside its own private context window. When an architect writes an Architecture Decision Record (ADR), updates a schema, or pushes an edge-case fix, other teammates' coding assistants have no idea. The result is silent architectural drift, broken contracts, and hours wasted reconciling pull requests.

We set out to fix this by building **OneContext**: an open architecture that gives every developer and every AI assistant on a project access to a single, real-time institutional memory bank. By anchoring our system on [Vectorize agent memory](https://vectorize.io/what-is-agent-memory) and the open-source [Hindsight](https://github.com/vectorize-io/hindsight) engine, we turned scattered developer context into an automatically synchronizing, conflict-aware knowledge plane.

Here is how we designed the system, the edge cases we hit when coordinating real-time memory across parallel IDEs, and the code patterns that made it work.

---

## What the System Does and How It Hangs Together

The goal of OneContext is simple: **One project. One memory. Every AI assistant.** 

Rather than building fragile editor plugins that try to intercept every keystroke, we designed OneContext as a lightweight, centralized memory orchestrator that interfaces with whichever tools developers already use.

The architecture comprises four core layers:

1. **Long-Term Memory Bank ([Hindsight](https://github.com/vectorize-io/hindsight))**: Every repository maps to exactly one isolated Hindsight bank (e.g., `onecontext-payments-core`). Every architectural decision, ingested specification chunk, and synchronized GitHub commit is retained here with rich metadata (`source_type`, `author`, `sha`, `timestamp`).
2. **Local Operational Metadata (SQLite)**: SQLite handles lightweight presence, team rooms with six-character join codes, audit logs, and supersession links. It does not store raw embeddings or semantic indexes; that stays in Hindsight.
3. **Real-Time Context Stream (FastAPI + Server-Sent Events)**: When any team member or automated worker captures a decision, ingests a document, or synchronizes a commit, an in-memory pub/sub broadcaster pushes the event to all connected teammates in under a second over SSE.
4. **Context Pack Engine**: Instead of forcing developers to leave their IDEs, OneContext compiles bounded, token-budgeted "Context Packs" tailored for Cursor rules, ChatGPT, or Claude. Teammates paste or pipe these packs directly into their prompts, guaranteeing their assistant builds against verified decisions.

---

## The Core Technical Challenge: Why Naive RAG Fails for Engineering Context

When software engineers think about giving AI tools memory, the default reaction is usually: *"Just throw our markdown files into a vector database with LangChain."*

We tried that early on. It falls apart in a real software team for three specific reasons:

### 1. Vector Similarity Has No Concept of Supersession
In software engineering, facts expire. In January, the team decides on PostgreSQL. In March, they evaluate Cassandra and reject it. In June, they migrate transactional ledger tables to CockroachDB. 

Under naive cosine similarity search, an engineer asking *"What database do we use for the ledger?"* frequently pulls the January PostgreSQL document or the Cassandra evaluation because those chunks contain high keyword overlap. Naive vector search cannot distinguish an active decision from an obsolete one.

### 2. Context Window Bloat and Prompt Fatigue
Dumping twenty architecture documents into a `.cursorrules` or `.systemprompt` file degrades autocomplete speed and burns tokens on irrelevant rules. Context must be filtered by relevance to the specific task and capped strictly to a budget (e.g., 3,000 characters).

### 3. Silent Contradictions
If a frontend engineer retains a note claiming an API endpoint uses snake_case, while the backend spec enforces camelCase, storing both creates a split-brain environment where assistants generate incompatible code on both sides of the boundary.

To solve this, we used [Hindsight docs](https://hindsight.vectorize.io/) to implement write-time conflict detection, explicit fact supersession, and clean memory recall.

---

## Code-Backed Implementation: How It Works Under the Hood

### 1. Resilient Thread-Local Client Management
OneContext is built on FastAPI and Python 3.13. Vectorize's Python SDK uses `aiohttp` for high-throughput HTTP connections. However, FastAPI handles synchronous route execution by offloading calls to worker threads via `anyio.to_thread.run_sync`. 

When an `aiohttp` ClientSession is initialized on the main application event loop during startup, and a subsequent worker thread attempts to run a synchronous recall or retain via an internal event loop, `aiohttp`'s internal timer triggers a `RuntimeError("Timeout context manager should be used inside a task")`.

To solve this across all endpoints, we wrapped Hindsight with a thread-local proxy in `backend/core/hindsight_client.py`:

```python
# backend/core/hindsight_client.py
from __future__ import annotations
import threading
from hindsight_client import Hindsight

class HindsightWrapper:
    """Wrapper around Hindsight client with thread-local session management."""

    def __init__(self, settings):
        self.base_url = settings.hindsight_base_url
        self.api_key = settings.hindsight_api_key
        self._local = threading.local()

    @property
    def client(self) -> Hindsight:
        """Get or initialize thread-local Hindsight client to avoid loop mismatches."""
        if not hasattr(self._local, "client") or self._local.client is None:
            self._local.client = Hindsight(
                base_url=self.base_url,
                api_key=self.api_key,
            )
        return self._local.client

    def recall(self, bank_id: str, query: str, max_results: int = 10):
        response = self.client.recall(bank_id=bank_id, query=query)
        results = getattr(response, "results", []) or []
        return [
            {
                "id": getattr(item, "id", ""),
                "text": getattr(item, "text", ""),
                "score": getattr(getattr(item, "scores", None), "semantic", None),
            }
            for item in results[:max_results]
        ]
```

This guarantees that each worker thread maintains its own active session, eliminating cross-thread loop collisions while keeping response latencies under 200ms.

---

### 2. Write-Time Conflict Detection and Event Broadcasting
When an engineer captures a decision, OneContext does not simply append the text blindly. It recalls the top three nearest semantic facts from Hindsight and evaluates whether the new statement contradicts existing institutional policies.

Here is the retention logic from `backend/core/memory_service.py`:

```python
# backend/core/memory_service.py
def retain(
    self,
    project_id: str,
    bank_id: str,
    text: str,
    agent_id: str = "user",
    source: str = "note",
    check_conflict: bool = True,
    metadata: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    now_iso = datetime.now(timezone.utc).isoformat()
    conflict_info = None

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
            c_mem = detected.get("conflicting_memory") or {}
            
            # Record conflict warning event in live room feed
            c_event = self.db.record_event(
                project_id=project_id,
                type="conflict",
                title="Memory Conflict Warning",
                body=f"Statement '{text}' conflicts with prior decision: '{c_mem.get('text', '')}'",
                author=agent_id,
            )
            if c_event:
                broadcaster.publish_nowait(project_id, c_event)

    # Retain fact in Vectorize Hindsight bank
    memory_id = self.hindsight.retain(
        bank_id=bank_id,
        text=text,
        metadata={**(metadata or {}), "source": source, "author": agent_id},
    )

    # Broadcast standard decision event to teammates
    event_type = "decision" if source in ("decision", "note", "user") else "document"
    d_event = self.db.record_event(
        project_id=project_id,
        type=event_type,
        title=text[:80] + ("..." if len(text) > 80 else ""),
        body=text,
        author=agent_id,
    )
    if d_event:
        broadcaster.publish_nowait(project_id, d_event)

    return {"memory_id": memory_id, "conflict": conflict_info}
```

If a contradiction is detected, an alert card immediately streams over SSE to every open browser window in the team room, preventing teammates from proceeding on contradictory assumptions.

---

### 3. Explicit Memory Corrections and Supersession
When a policy legitimately changes, an engineer can supersede an obsolete decision. We track the supersession in Hindsight metadata and locally in SQLite to ensure subsequent recall queries purge stale observations:

```python
# backend/features/corrections.py
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
    now_iso = datetime.now(timezone.utc).isoformat()

    # 1. Retain replacement memory in Hindsight with supersedes link
    retain_res = self.service.retain(
        project_id=project_id,
        bank_id=bank_id,
        text=new_text,
        agent_id=agent_id,
        source="correction",
        check_conflict=False,  # deliberate update
        metadata={
            "supersedes": old_memory_id,
            "superseded_text": old_memory_text[:200] if old_memory_text else "",
            "correction_reason": reason,
        },
    )

    # 2. Persist supersession relationship to filter out derived facts
    self.db.record_correction(
        project_id=project_id,
        old_memory_id=old_memory_id,
        new_memory_id=retain_res["memory_id"],
        reason=reason,
        old_memory_text=old_memory_text,
        created_at=now_iso,
    )
    return {"status": "corrected", "new_memory_id": retain_res["memory_id"]}
```

---

### 4. Compiling Clean, Assistant-Specific Context Packs
Rather than dumping an entire chat transcript into a prompt, our Context Pack generator queries Hindsight for the task at hand, removes superseded decisions, deduplicates redundant text chunks, and formats the result cleanly within a strict character boundary:

```python
# backend/api/memory.py
@router.post("/context-pack", response_model=ContextPackResponse)
def get_context_pack(
    project_id: str,
    payload: ContextPackRequest,
    memory_service=Depends(get_memory_service),
) -> ContextPackResponse:
    project = get_project_or_404(project_id)
    bank_id = project["bank_id"]

    recalled = memory_service.recall(
        project_id=project_id,
        bank_id=bank_id,
        query=payload.task,
        max_results=15,
        include_superseded=False,
    )

    superseded_info = local_db.get_superseded_info(project_id)
    active_facts = []
    seen = set()

    for m in recalled:
        m_id = m.get("id")
        m_text = m.get("text", "").strip()
        if not m_text or m_id in superseded_info["ids"]:
            continue
        if m_text.lower() in seen:
            continue
        seen.add(m_text.lower())
        active_facts.append(m_text)

    # Format into assistant-specific wrappers (Cursor rules vs ChatGPT)
    facts_block = "\n".join([f"- {fact}" for fact in active_facts])
    if payload.target.lower() == "cursor":
        pack_text = (
            f"# Cursor Project Rules: {project['name']}\n"
            f"# Key decisions relevant to: {payload.task}\n"
            f"{facts_block}\n# END RULES\n\n{payload.task}"
        )
    else:
        pack_text = (
            f"[PROJECT CONTEXT: {project['name']}]\n"
            f"Key decisions and facts relevant to: {payload.task}\n"
            f"{facts_block}\n[END CONTEXT]\n\n{payload.task}"
        )

    return ContextPackResponse(
        project_id=project_id,
        project_name=project["name"],
        target=payload.target,
        pack=pack_text[:payload.max_chars],
        char_count=len(pack_text[:payload.max_chars]),
        task=payload.task,
    )
```

---

## Results in Action: What Happens in a Real Team Room

Here is how this behaves during everyday development:

### 1. Zero-Friction Multi-User Sync
Engineer Alice creates a team room called `Payments Core` and receives a 6-character code (`1HQ7HE`). Teammate Bob enters that code in a separate browser window. 

Alice’s sidebar immediately lights up with a green presence indicator: `🟢 Bob (online)`. Both engineers are now pointing to the exact same Hindsight memory bank.

### 2. Live Broadcast of Architectural Decisions
Bob receives an update from third-party payment partner Stripe regarding webhook verification. In his right panel, he captures:
> *"All outbound merchant webhooks must use HMAC-SHA256 signatures with timestamp anti-replay validation within a 300-second drift window."*

Within **600 milliseconds**, the decision streams across SSE into Alice's Live Context Feed with a purple `DECISION` badge and Bob's name.

### 3. Immediate Catch-Up Summaries
When teammate Carol returns from lunch, she clicks **⚡ Catch Me Up Now**. OneContext queries all events recorded since her last recorded catch-up and passes them to Groq at temperature 0 with strict summarization constraints:

```markdown
**Decisions**
- Webhook signatures: HMAC-SHA256 with timestamp anti-replay validation (drift <= 300s).

**Architecture or doc changes**
- None.

**Commits**
- Commit 8a2f1b4: Updated payment gateway session timeout configuration.
```

Carol is caught up in five seconds without asking anyone in Slack.

### 4. Code Generation Grounded in Verifiable Memory
Bob switches to the **Collaborative IDE** and prompts the vibe-coding bar:
> *"Write the FastAPI webhook verification middleware."*

Groq synthesizes the code. But before the draft is presented, OneContext runs our built-in Validator Agent against the Hindsight memory bank. The validator inspects the draft, confirms that HMAC-SHA256 and the 300-second drift window are present, and marks the code `validation: valid`.

---

## Lessons Learned

Building a collaborative memory layer taught us several counterintuitive lessons about AI in engineering teams:

### 1. Memory Supersession Matters More Than Vector Depth
Most vector pipelines focus on embedding quality and retrieval depth ($k=20, 50$). In production engineering, the hardest problem is **invalidation**. A model given three highly relevant facts where one is an outdated draft will hallucinate conflicting code half the time. Building explicit supersession tracking into your memory schema is non-negotiable.

### 2. Context Packs Beat Direct IDE Plugins for Usability
Early on, we considered building heavy IDE extensions. But developers are protective of their editor setups and frequently switch between Cursor, terminal agents, and web interfaces. Providing a compact, clean **Context Pack** that compiles directly to clipboard rules gave us 100% assistant compatibility on day one without maintaining separate extensions.

### 3. Write-Time Conflict Detection Prevents Tech Debt Early
Catching a conflicting decision at the moment of retention is dramatically cheaper than discovering it during code review. Querying Hindsight for the top three nearest neighbors at retain time and running a zero-temperature LLM check takes under 400ms, but saves hours of refactoring downstream.

### 4. Background Sync Keeps Documentation Alive
Developers rarely update wiki pages manually. By running a background worker that polls GitHub repository commits every 45 seconds and retains commit messages with author metadata into Hindsight, our project memory stays current even when developers forget to log ADRs explicitly.

---

## Conclusion

AI assistants are only as good as the context they receive. Leaving every developer to manually maintain their own system prompts guarantees that team members will build diverging architectures.

By centralizing long-term project memory in [Vectorize Hindsight](https://github.com/vectorize-io/hindsight), our team gave every engineer—and every AI assistant they run—a single, verifiable source of truth.

---

### Resources & Links

- **Vectorize Hindsight Repository**: [github.com/vectorize-io/hindsight](https://github.com/vectorize-io/hindsight)
- **Hindsight Technical Documentation**: [hindsight.vectorize.io](https://hindsight.vectorize.io/)
- **Understanding Vectorize Agent Memory**: [vectorize.io/what-is-agent-memory](https://vectorize.io/what-is-agent-memory)
