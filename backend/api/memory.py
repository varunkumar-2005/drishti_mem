# backend/api/memory.py
# FastAPI router for memory operations.
# Endpoints: POST /memory/retain, POST /memory/recall, POST /memory/ask.
# Delegates to memory_service for all Hindsight + Groq orchestration.
