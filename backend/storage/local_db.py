# backend/storage/local_db.py
# SQLite persistence layer (via Python's built-in sqlite3 or SQLAlchemy).
# Tables: projects, agents, audit_log.
# Keeps lightweight local state separate from Hindsight's vector store.
