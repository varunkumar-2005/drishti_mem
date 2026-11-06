# backend/core/llm_client.py
# Groq inference client.
# Handles model selection, fallback to a secondary model on error,
# rate-limit retries, and prompt formatting.
