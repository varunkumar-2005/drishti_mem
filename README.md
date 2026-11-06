# OneContext

> **Give every AI agent a shared, searchable long-term memory — powered by Hindsight and Groq.**

## What is OneContext?

OneContext is a backend + frontend platform that lets multiple AI agents (Planner, Coder, Validator, …) share a single memory bank per project. Agents *retain* decisions, code choices, and lessons learned; any agent can later *recall* relevant context before answering — eliminating repeated mistakes and forgotten context.

## Architecture

```
Frontend (React)
     │  REST
     ▼
FastAPI Backend
  ├── /projects  — one memory bank per project
  ├── /memory    — retain · recall · ask
  └── /agents    — register & manage agents
        │
        ├── core/hindsight_client.py  ← Hindsight retain/recall
        ├── core/llm_client.py        ← Groq inference
        └── core/memory_service.py    ← orchestration heart
```

## How Hindsight is Used

| Operation | Hindsight call | When |
|-----------|---------------|------|
| **Retain** | `client.retain(text, project_id)` | Agent stores a decision / fact |
| **Recall** | `client.recall(query, project_id)` | Before answering, fetch relevant memories |
| **Ask** | recall → Groq prompt | End-to-end RAG answer |

## Quick Start

```bash
cp .env.example .env        # add your keys
pip install -r requirements.txt
uvicorn backend.main:app --reload
```

Then open `http://localhost:8000/docs` for the interactive API explorer.
