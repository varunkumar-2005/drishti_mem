# backend/core/hindsight_client.py
# Thin wrapper around the hindsight-client SDK.
# Exposes retain(text, project_id) and recall(query, project_id) helpers
# with connection setup, error handling, and optional retry logic.
