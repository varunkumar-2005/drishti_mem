# OneContext

> **One project. One memory. Every AI assistant.**

OneContext is a project memory platform for software engineering. It provides a shared, searchable, and collision-resistant memory bank in **Vectorize Hindsight Cloud** that any AI assistant (ChatGPT, Claude, Cursor, Codex) can use through compact, accurate context packs.

---

## The Problem

Modern software engineering teams are rapidly adopting specialized AI agents for planning, code generation, testing, and compliance. However, these agents typically operate in **stateless silos**:

1. **Context Drift**: Agent 1 (Planner) decides to standardize on PostgreSQL with async SQLAlchemy, but Agent 2 (Builder) independently starts building services with MongoDB.
2. **Repeated Context Injection**: Teams waste thousands of tokens constantly re-prompting every agent with the same architecture standards, naming conventions, and incident lessons.
3. **Undetected Policy Collisions**: When a new PR contradicts a compliance rule (e.g. dual-officer sign-off on payouts over $10,000), ungrounded review agents approve the code because they lack institutional memory.

---

## The Solution

**OneContext connects every project to a dedicated Hindsight memory bank.** 

- **Autonomous Coordination**: Agent 1 retains an architectural decision; Agent 2 discovers it purely via semantic recall without manual handoffs.
- **Continuous Compliance**: Agent 3 (Validator) cross-checks pull requests and technical proposals against the project's recorded memory bank to flag violations before merge.
- **Collision Detection on Retain**: When an agent attempts to store a decision that contradicts an existing policy (e.g. migrating REST to GraphQL), OneContext detects the contradiction in real time and alerts the team.
- **Clean Supersession**: When a policy genuinely evolves, the `/correct` endpoint supersedes the old memory and purges all derived atomic sub-facts from active retrieval.

---

## Key Features

- **Side-by-Side Before/After Benchmarking**: Real-time visual comparison proving the qualitative difference between generic ungrounded LLMs and Hindsight-grounded responses.
- **Author Attribution & Vector Scoring**: Every recalled memory clearly displays its author agent badge (`db-architect`, `security-lead`), source category, and authentic Hindsight semantic score (`scores.semantic`).
- **Conflict Warning Cards**: Visual side-by-side alert banner in the Memory Explorer highlighting contradicting policies with single-click supersession.
- **Resilient Fallback Circuit**: Automated 3x exponential retry and graceful model fallback on Groq Cloud.
- **Append-Only Audit Trail**: Full local SQLite tracking of every retain, recall, validate, and correction event.

---

## How Hindsight Memory Is Used

All long-term episodic, world, and observation knowledge lives in **Vectorize Hindsight Cloud**. The local SQLite database stores **only** project metadata and audit logs.

| Operation | Hindsight SDK Call | Purpose | Primary Implementation File |
|---|---|---|---|
| **Bank Creation** | `client.create_bank(bank_id, name, mission)` | Provisions an isolated memory bank per project (`onecontext-{project_id}`). | [`backend/core/hindsight_client.py`](file:///c:/Users/Suresh/Desktop/one_mem/onecontext/backend/core/hindsight_client.py) |
| **Retain** | `client.retain(bank_id, content, metadata)` | Persists an engineering standard with author, source, and timestamp metadata. | [`backend/core/memory_service.py`](file:///c:/Users/Suresh/Desktop/one_mem/onecontext/backend/core/memory_service.py) |
| **Semantic Recall** | `client.recall(bank_id, query)` | Retrieves relevant decisions with cross-encoder semantic scores (`scores.semantic`). | [`backend/core/hindsight_client.py`](file:///c:/Users/Suresh/Desktop/one_mem/onecontext/backend/core/hindsight_client.py) |
| **Conflict Detection** | `client.recall(...)` + LLM eval at `temp=0.0` | Cross-checks proposed memories against active policies before persisting. | [`backend/features/conflict_detection.py`](file:///c:/Users/Suresh/Desktop/one_mem/onecontext/backend/features/conflict_detection.py) |
| **Memory Correction** | `client.retain(..., metadata={"supersedes": id})` | Stores updated policy and marks older facts as historically superseded. | [`backend/features/corrections.py`](file:///c:/Users/Suresh/Desktop/one_mem/onecontext/backend/features/corrections.py) |
| **Decomposed Exclusion** | Token overlap & keyword extraction | Prevents sub-clauses extracted by Hindsight from leaking into active RAG context. | [`backend/core/memory_service.py`](file:///c:/Users/Suresh/Desktop/one_mem/onecontext/backend/core/memory_service.py) |

---

## Tools Used (Honest & Transparent)

- **[Vectorize Hindsight](https://hindsight.vectorize.io)** (`hindsight-client`): The core long-term memory engine providing semantic vector search, temporal reasoning, and entity knowledge graph decomposition.
- **[Groq SDK](https://groq.com)**: Ultra-fast LLM inference:
  - **Primary Model**: `openai/gpt-oss-120b` for complex synthesis and validator reasoning.
  - **Fallback Model**: `qwen/qwen3.8-27b` for automated high-availability fallback. *(Note: `qwen/qwen3-32b` returned an HTTP 404 on our Groq key, so `qwen/qwen3.8-27b` was verified and configured as the working fallback).*
- **Google Antigravity IDE**: AI-assisted development and pair-programming environment used throughout system construction.
- **FastAPI (Python 3.11+)**: Clean, typed asynchronous backend architecture with Pydantic v2 schemas.
- **React 18 + Vite**: High-contrast, dark-mode web console designed for clear presentation and observability.
- **Band Desktop**: Band Desktop was installed during development; however, its agent runtimes failed to start on our Windows testing environment (`Runtime startup failed`), so it is not part of the active production runtime.

---

## Known Limitations

1. **LLM-Based Conflict Detection & Validation**: Policy comparison and PR validation rely on Groq LLM inferences at `temperature=0.0`. While highly consistent, LLM-based judgments can occasionally produce edge-case false positives or subtle phrasing variances.
2. **Decomposed Knowledge Extraction**: Hindsight automatically breaks complex multi-clause sentences into multiple discrete facts and entity observations. Superseding a memory requires semantic and keyword-level exclusion to purge all derived sub-facts.
3. **Asynchronous Indexing Delay**: Vectorize Hindsight indexes retained memories asynchronously. While queries usually index within 2 to 4 seconds, test suites and instant queries require a short polling wait helper (`wait_for_recall`).
4. **Access Permissions Scope**: Fine-grained per-agent read/write RBAC permissions were deprioritized in this release in order to focus engineering time on conflict detection and memory integrity.
5. **Validator Test Sample**: The validator agent was validated through a dedicated 6-run stress test and automated pytest suites; production deployments would benefit from broader benchmark evaluations.

---

## Quick Start on Windows

### 1. Prerequisites
- **Python 3.11+** installed
- **Node.js 18+** and **npm** installed

### 2. Configure Environment Variables
Copy `.env.example` to `.env` in the `onecontext/` directory:
```bash
cp .env.example .env
```
Fill in your credentials (keys are never committed to git):
```ini
HINDSIGHT_API_KEY=your_hindsight_api_key_here
HINDSIGHT_BASE_URL=https://api.hindsight.vectorize.io

GROQ_API_KEY=your_groq_api_key_here
GROQ_PRIMARY_MODEL=openai/gpt-oss-120b
GROQ_FALLBACK_MODEL=qwen/qwen3.8-27b
```

### 3. Launch OneContext (1-Click)
Double-click **[`start_app.bat`](file:///C:/Users/Suresh/Desktop/one_mem/start_app.bat)** in the root folder.

*Or start the servers manually in separate PowerShell windows:*

#### Terminal 1 — Backend:
```powershell
cd onecontext
& "C:\Users\Suresh\AppData\Local\Programs\Python\Python313\Scripts\uvicorn.exe" backend.main:app --reload --port 8000
```

#### Terminal 2 — Frontend:
```powershell
cd onecontext\frontend
npm run dev
```

Open **`http://localhost:5173`** in your browser.

---

## Seed Data & Automated Tests

### Seed Realistic Fintech Decisions
OneContext includes an idempotent seed script that populates 18 realistic engineering decisions simulating *ApexPay Technologies* (a 12-engineer payments startup):
```powershell
cd onecontext
& "C:\Users\Suresh\AppData\Local\Programs\Python\Python313\python.exe" scripts/seed_data.py
```
*(Running the script multiple times is 100% safe: existing decisions are automatically skipped).*

### Run Pytest Test Suite
To run all 20 unit and integration tests:
```powershell
cd onecontext
& "C:\Users\Suresh\AppData\Local\Programs\Python\Python313\python.exe" -m pytest -v
```

---

## Live Demo Walkthrough (3 Minutes)

1. **Before/After Grounding**: Open `http://localhost:5173` to the **Before / After** panel. Click the preset question *"What is our policy for transactions above $10,000?"*. Observe the left column offering generic ungrounded advice, while the right column cites the exact dual-officer sign-off policy with author badges and vector score.
2. **Cross-Agent Collaboration**: Under the **Agents** tab, run the **Planner** to standardize PostgreSQL, then run the **Builder** to design the ledger. Builder autonomously aligns with Planner without manual prompt passing.
3. **Automated QA Validation**: Paste a PR proposing MongoDB into the **Validator** card. The validator recalls Hindsight memory and catches the contradiction.
4. **Collision Prevention**: In **Memory Explorer**, click **+ Retain New Memory** and submit a REST to GraphQL migration proposal. A yellow **Warning Card** flags the contradiction against the existing REST standard.
5. **Memory Correction**: Click **✏️ Correct this memory** to update the decision to REST v2. Ask the question again in Chat to observe the new policy taking precedence.

---

## Project Structure

```text
onecontext/
├── backend/
│   ├── main.py                  # FastAPI server, lifespan events, CORS
│   ├── config.py                # Pydantic v2 settings loading .env
│   ├── core/
│   │   ├── hindsight_client.py  # ONLY file importing official Hindsight SDK
│   │   ├── llm_client.py        # Groq client with retry and fallback model
│   │   └── memory_service.py    # Retain, recall, grounded RAG, and deduplication
│   ├── agents/
│   │   ├── base_agent.py        # Base agent with automated agent_id tagging
│   │   ├── agent_one.py         # Agent 1 (Planner): establishes standards
│   │   ├── agent_two.py         # Agent 2 (Builder): discovers standards via recall
│   │   └── validator_agent.py   # Agent 3 (Validator): catches contradictory PRs
│   ├── features/
│   │   ├── conflict_detection.py# LLM-based policy conflict detector (temp=0.0)
│   │   ├── corrections.py       # Memory supersession and historical updates
│   │   └── attribution.py       # Source attribution and Hindsight score formatting
│   ├── api/                     # Scoped FastAPI routes (/projects, /retain, /recall)
│   └── storage/
│       └── local_db.py          # SQLite metadata (projects, agents, audit, corrections)
├── frontend/
│   ├── src/
│   │   ├── components/          # BeforeAfterPanel, MemoryCard, ChatBox
│   │   ├── pages/               # Dashboard, MemoryExplorer, Agents, SearchHistory
│   │   └── api/client.js        # Axios API client
├── scripts/
│   ├── verify_setup.py          # Phase 1 sanity check
│   ├── seed_data.py             # Idempotent 18-decision fintech seeder
│   ├── demo_before_after.py     # End-to-end 3-agent terminal demonstration
│   └── stress_test_validator.py # 6-run validator determinism verification
├── tests/                       # 20 automated pytest unit & integration tests
├── docs/
│   ├── ARCHITECTURE.md          # Deep-dive architecture and Mermaid diagrams
│   └── DEMO_SCRIPT.md           # 3-minute timed presenter script
├── run_backend.bat              # Windows backend launcher
├── run_frontend.bat             # Windows frontend launcher
└── start_app.bat                # 1-click dual-server launcher
```

---

## License

MIT License. Designed and engineered for production software engineering teams.
