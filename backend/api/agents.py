# backend/api/agents.py
# FastAPI router for agent management.
# Endpoints: POST /agents (register), GET /agents (list), DELETE /agents/{id}.
# Agents are scoped to a project and use that project's shared memory.
