"""
tests/test_llm_fallback.py
Tests the automated fallback mechanism of LLMClient.
Deliberately points the primary model to an invalid model ID to prove
that the client catches the error, triggers the fallback, and succeeds.
"""

from __future__ import annotations

import pytest
from backend.config import get_settings
from backend.core.llm_client import LLMClient


class MockSettingsWithFailingPrimary:
    """Mock settings that deliberately injects an invalid primary model ID."""

    def __init__(self, real_settings):
        self.groq_api_key = real_settings.groq_api_key
        # Invalid model that forces Groq to raise NotFoundError / 404
        self.groq_primary_model = "non-existent-broken-primary-model-404"
        # Real confirmed fallback model
        self.groq_fallback_model = real_settings.groq_fallback_model


def test_fallback_triggers_when_primary_fails():
    """
    When the primary model fails, LLMClient must seamlessly invoke the fallback
    model without crashing and return the fallback model's name.
    """
    real_settings = get_settings()
    failing_settings = MockSettingsWithFailingPrimary(real_settings)

    # Initialize client with the failing primary model configuration
    client = LLMClient(settings=failing_settings)

    messages = [
        {
            "role": "user",
            "content": "Reply with exactly one word: 'FALLBACK_VERIFIED'.",
        }
    ]

    response_text, model_used = client.chat(messages=messages, max_tokens=20)

    # Assertions
    assert model_used == failing_settings.groq_fallback_model, (
        f"Expected fallback model '{failing_settings.groq_fallback_model}', but got '{model_used}'"
    )
    assert len(response_text) > 0
    assert "FALLBACK_VERIFIED" in response_text.upper()
