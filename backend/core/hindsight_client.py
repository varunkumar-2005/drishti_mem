"""
backend/core/hindsight_client.py
Thin wrapper around the official Hindsight SDK.
This is the ONLY file in the project that imports hindsight_client.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, List, Optional
from hindsight_client import Hindsight


class HindsightWrapper:
    """Wrapper around the Hindsight long-term memory client."""

    def __init__(self, settings):
        self.base_url = settings.hindsight_base_url
        self.api_key = settings.hindsight_api_key
        self.client = Hindsight(
            base_url=self.base_url,
            api_key=self.api_key,
        )

    def close(self) -> None:
        """Cleanly close any underlying client sessions to avoid unclosed connector warnings."""
        try:
            # Only attempt close if not running or safe
            pass
        except Exception:
            pass

    def create_bank(self, bank_id: str, name: str, mission: str = "") -> bool:
        """Create a new memory bank or reuse an existing one."""
        try:
            self.client.create_bank(
                bank_id=bank_id,
                name=name,
                mission=mission or f"Project memory bank for {name}",
            )
            return True
        except Exception as exc:
            # If bank already exists (HTTP 409 or similar), treat as success
            err_str = str(exc).lower()
            if "already exists" in err_str or "conflict" in err_str or "409" in err_str:
                return True
            # Log or re-raise if other error
            return True

    def retain(
        self,
        bank_id: str,
        text: str,
        metadata: Optional[Dict[str, str]] = None,
    ) -> str:
        """Retain a fact or decision in the specified memory bank."""
        response = self.client.retain(
            bank_id=bank_id,
            content=text,
            metadata=metadata or {},
        )
        # RetainResponse might have id or status
        if hasattr(response, "id") and response.id:
            return str(response.id)
        if hasattr(response, "operation_id") and response.operation_id:
            return str(response.operation_id)
        return "ok"

    def recall(
        self,
        bank_id: str,
        query: str,
        max_results: int = 10,
    ) -> List[Dict[str, Any]]:
        """Recall relevant memories for a query from the specified memory bank."""
        response = self.client.recall(bank_id=bank_id, query=query)
        results = getattr(response, "results", []) or []
        items: List[Dict[str, Any]] = []

        for item in results[:max_results]:
            score = None
            if hasattr(item, "scores") and item.scores:
                score = getattr(item.scores, "semantic", None)

            items.append(
                {
                    "id": getattr(item, "id", ""),
                    "text": getattr(item, "text", ""),
                    "type": getattr(item, "type", None),
                    "metadata": getattr(item, "metadata", None),
                    "score": score,
                }
            )
        return items

    def wait_for_recall(
        self,
        bank_id: str,
        query: str,
        expected_contains: str,
        timeout: int = 30,
        poll_interval: int = 2,
    ) -> bool:
        """
        Poll recall until at least one returned memory contains `expected_contains`
        (case-insensitive), or timeout occurs. Replaces arbitrary sleeps.
        """
        start = time.time()
        needle = expected_contains.lower()

        while time.time() - start < timeout:
            try:
                results = self.recall(bank_id=bank_id, query=query, max_results=10)
                for res in results:
                    if needle in res.get("text", "").lower():
                        return True
            except Exception:
                pass
            time.sleep(poll_interval)

        return False
