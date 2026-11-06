"""
backend/core/llm_client.py
Groq inference client with automated retry and fallback model support.
This is the ONLY file in the project that imports groq.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Tuple
from groq import Groq

logger = logging.getLogger(__name__)


class LLMClient:
    """Wrapper around the Groq SDK with automatic fallback handling."""

    def __init__(self, settings):
        self.api_key = settings.groq_api_key
        self.primary_model = settings.groq_primary_model
        self.fallback_model = settings.groq_fallback_model
        self.client = Groq(api_key=self.api_key)

    def chat(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 512,
        temperature: float = 0.2,
    ) -> Tuple[str, str]:
        """
        Send a chat completion request.
        Attempts primary model first; falls back to secondary model on any failure.
        Returns: (response_text, model_name_used)
        """
        models_to_try = [self.primary_model, self.fallback_model]
        errors = []

        for model in models_to_try:
            try:
                response = self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                content = response.choices[0].message.content or ""
                return content.strip(), model
            except Exception as exc:
                err_msg = f"Model {model} failed: {type(exc).__name__}: {exc}"
                logger.warning(err_msg)
                errors.append(err_msg)

        raise RuntimeError(f"All LLM models failed. Errors: {'; '.join(errors)}")
