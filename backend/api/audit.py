# backend/api/audit.py
# FastAPI router for the memory audit trail.
# Endpoints: GET /audit/{project_id} — returns timestamped retain/recall history.
# Powers the SearchHistory page in the frontend.
