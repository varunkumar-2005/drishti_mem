# OneContext Architecture & Technical Specification

> **One project. One memory. Every agent.**

OneContext provides a shared, long-term memory layer for autonomous AI agents and human software engineers. By attaching every engineering project to a dedicated memory bank on **Vectorize Hindsight Cloud**, OneContext eliminates context drift, prevents contradictory AI decisions, and enforces architectural compliance across distributed agent workflows.

---

## 1. System Overview & Architecture Diagram

```mermaid
flowchart TD
    subgraph UI ["Client Layer (React 18 + Vite)"]
        BAPanel["Before / After Panel"]
        MemExp["Memory Explorer & Conflict Cards"]
        AgentDash["Agent Orchestration Console"]
        AuditUI["Audit Trail Viewer"]
    end

    subgraph API ["FastAPI Application Layer (backend/api)"]
        ProjectsAPI["/projects (CRUD & Bank Scoping)"]
        MemoryAPI["/projects/{id}/retain, /recall, /ask"]
        CorrectAPI["/projects/{id}/correct (Supersession)"]
        ConflictAPI["/projects/{id}/check-conflict"]
        AgentsAPI["/projects/{id}/agents/{agent_id}/run"]
        ValidateAPI["/projects/{id}/validate (Compliance)"]
    end

    subgraph Core ["Core Services (backend/core & backend/features)"]
        MemService["MemoryService (backend/core/memory_service.py)"]
        ConflictDet["ConflictDetector (backend/features/conflict_detection.py)"]
        Corrections["CorrectionsManager (backend/features/corrections.py)"]
        Attribution["AttributionFormatter (backend/features/attribution.py)"]
        HindsightWrap["HindsightWrapper (backend/core/hindsight_client.py)"]
        LLMWrap["LLMClient (backend/core/llm_client.py)"]
    end

    subgraph Agents ["Multi-Agent System (backend/agents)"]
        Agent1["Agent 1: Planner\n(Standardizes & Retains Decisions)"]
        Agent2["Agent 2: Builder\n(Recalls Decisions via Hindsight)"]
        Agent3["Agent 3: Validator\n(Cross-Checks PRs Against Memory)"]
    end

    subgraph MemoryStore ["Vectorize Hindsight Cloud (Official SDK)"]
        HindsightBank["Project Memory Bank: onecontext-{project_id}"]
        WorldFacts["World & Episodic Facts"]
        EntityObs["Entity Observations & Knowledge Graph"]
        VecScores["Semantic Vector Scoring (scores.semantic)"]
    end

    subgraph LLMStore ["Groq Ultra-Fast Inference"]
        PrimaryModel["Primary: openai/gpt-oss-120b"]
        FallbackModel["Fallback: qwen/qwen3.8-27b"]
        AutoRetry["Automated 3x Exponential Retry Circuit"]
    end

    subgraph LocalMeta ["Local Metadata Store (SQLite: onecontext.db)"]
        TableProj["projects (id, name, bank_id, created_at)"]
        TableAgents["agents (id, project_id, name, role)"]
        TableAudit["audit_log (retain, recall, correct, conflict_detected)"]
        TableCorr["corrections (old_id, old_text, new_id, reason)"]
    end

    %% Interactions
    UI -->|HTTP / JSON| API
    API --> Core
    Agents -->|Uses memory_service| Core

    Agent1 -->|1. Retain Decision| MemService
    Agent2 -->|2. Semantic Recall| MemService
    Agent3 -->|3. Validate Draft| MemService

    MemService --> HindsightWrap
    MemService --> LLMWrap
    ConflictDet --> LLMWrap
    Corrections --> MemService

    HindsightWrap -->|HTTPS / REST API| MemoryStore
    LLMWrap -->|Chat Completions| LLMStore
    Core --> LocalMeta

    classDef memory fill:#1e3a8a,stroke:#3b82f6,color:#ffffff,stroke-width:2px;
    classDef llm fill:#064e3b,stroke:#10b981,color:#ffffff,stroke-width:2px;
    classDef sqlite fill:#374151,stroke:#9ca3af,color:#ffffff,stroke-width:1px;

    class HindsightBank,WorldFacts,EntityObs,VecScores memory;
    class PrimaryModel,FallbackModel,AutoRetry llm;
    class TableProj,TableAgents,TableAudit,TableCorr sqlite;
```

---

## 2. Core Architecture Invariants

1. **Isolation by Design**: All actual memory content, fact extraction, semantic embeddings, and observations reside in **Vectorize Hindsight Cloud**.
2. **Local DB Scope**: The local SQLite database (`onecontext.db`) stores **only** system metadata: project definitions, registered agent profiles, supersession mappings, and an append-only audit trail. Real project knowledge is never duplicated into SQLite.
3. **Dedicated Hindsight Wrapper**: All interactions with Hindsight are encapsulated inside [`backend/core/hindsight_client.py`](file:///c:/Users/Suresh/Desktop/one_mem/onecontext/backend/core/hindsight_client.py). No other file imports `hindsight-client` directly.
4. **No Manual Agent Handoffs**: Agent 2 (Builder) and Agent 3 (Validator) receive zero context from Agent 1 (Planner) via prompts, parameters, or session memory. Cross-agent coordination happens **strictly** via semantic recall against the shared Hindsight bank.
5. **Authentic Data Integrity**: Hindsight returns real semantic match scores via `scores.semantic` on `RecallResult`. OneContext surfaces these exact values directly in the UI (`Score: 0.XX`) without fabricating percentages or artificial metrics.

---

## 3. Data Flow & Execution Lifecycles

### 3.1 Decision Retention & Automated Conflict Detection
```mermaid
sequenceDiagram
    autonumber
    actor Engineer as Engineer / Agent 1
    participant API as /projects/{id}/retain
    participant MS as MemoryService
    participant CD as ConflictDetector
    participant HW as HindsightWrapper
    participant LLM as Groq LLM
    participant DB as SQLite LocalDB

    Engineer->>API: POST /retain (text, agent_id, source)
    API->>MS: retain(text, check_conflict=True)
    MS->>HW: recall(query=text, max_results=3)
    HW-->>MS: [recalled existing memories]
    MS->>CD: detect_conflict(text, existing_memories)
    CD->>LLM: evaluate contradiction at temperature 0.0
    LLM-->>CD: {"has_conflict": true/false, "explanation": "..."}
    alt Contradiction Detected
        CD->>DB: log_audit(action="conflict_detected", details)
    end
    MS->>HW: retain(content=text, metadata={agent_id, source, timestamp})
    HW-->>MS: memory_id
    MS->>DB: log_audit(action="retain", text, agent_id)
    MS-->>API: RetainResponse (memory_id, conflict_detail)
    API-->>Engineer: 200 OK + Conflict Alert
```

### 3.2 Grounded Answering (`/ask`) with Supersession Filtering
When a question is asked:
1. `MemoryService.recall()` queries Hindsight with `include_superseded=False`.
2. OneContext checks the SQLite `corrections` registry to identify superseded memory IDs and original superseded source texts.
3. **Multi-Fact Derivation Exclusion**: Any atomic fact or entity observation derived from a superseded decision is purged from active retrieval.
4. The remaining active facts are compiled into an authoritative context block:
   ```text
   === PROJECT MEMORY CONTEXT ===
   [1] (Source: architecture_decision, Author: db-architect)
   DECISION: Standardize all transactional persistence on PostgreSQL 16 using asyncpg...
   ==============================
   ```
5. Groq (`openai/gpt-oss-120b`) synthesizes a grounded answer citing the active decisions.
6. The operation is logged in the audit trail (`action="ask"`).

### 3.3 Memory Correction & Historical Supersession (`/correct`)
When an architectural standard changes (e.g. reverting an experimental proposal):
1. The user or agent invokes `POST /projects/{id}/correct` with `old_memory_id`, `new_text`, and `reason`.
2. The new memory is ingested into Hindsight carrying metadata `{"supersedes": old_memory_id, "reason": reason}`.
3. The relationship is recorded in SQLite's `corrections` table alongside `old_memory_text`.
4. Subsequent recalls automatically exclude both the old memory ID and all sub-facts derived from the original text, ensuring total alignment across all agents.

---

## 4. Multi-Agent System Roles

| Agent | Module | Role | Hindsight Interaction |
|---|---|---|---|
| **Agent 1: Planner** | [`backend/agents/agent_one.py`](file:///c:/Users/Suresh/Desktop/one_mem/onecontext/backend/agents/agent_one.py) | Formulates architectural policies, database choices, compliance limits | Writes decisions to Hindsight with `agent_id: agent-planner` |
| **Agent 2: Builder** | [`backend/agents/agent_two.py`](file:///c:/Users/Suresh/Desktop/one_mem/onecontext/backend/agents/agent_two.py) | Generates implementation plans and technical specifications | Discovers standards strictly via semantic recall from Hindsight |
| **Agent 3: Validator** | [`backend/agents/validator_agent.py`](file:///c:/Users/Suresh/Desktop/one_mem/onecontext/backend/agents/validator_agent.py) | Reviews pull requests and code proposals for compliance | Recalls project decisions, detects contradictions, flags violations |

---

## 5. Resilient LLM Inference Engine

OneContext implements an automatic fallback circuit inside [`backend/core/llm_client.py`](file:///c:/Users/Suresh/Desktop/one_mem/onecontext/backend/core/llm_client.py):
- **Primary Model**: `openai/gpt-oss-120b` (on Groq Cloud) for complex reasoning and synthesis.
- **Fallback Model**: `qwen/qwen3.8-27b` (on Groq Cloud) for high-throughput resilience.
- **Retry Logic**: If the primary model encounters rate limits (HTTP 429), gateway timeouts (HTTP 504), or internal errors, the client retries with exponential backoff before cleanly switching to the fallback model.
- **Model Tracking**: Every API response records the exact `model_used` in its response metadata for full observability.

---

## 6. Local SQLite Schema (`onecontext.db`)

```sql
CREATE TABLE projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    bank_id TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE agents (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    name TEXT NOT NULL,
    role TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (project_id) REFERENCES projects(id)
);

CREATE TABLE audit_log (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    action TEXT NOT NULL,  -- retain, recall, ask, validate, correct, conflict_detected
    query_or_text TEXT,
    result_count INTEGER DEFAULT 0,
    timestamp TEXT NOT NULL
);

CREATE TABLE corrections (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    old_memory_id TEXT NOT NULL,
    old_memory_text TEXT,
    new_memory_id TEXT NOT NULL,
    reason TEXT,
    created_at TEXT NOT NULL
);
```
