"""
backend/core/broadcaster.py
In-memory pub/sub event broadcaster for Server-Sent Events (SSE).
Allows live room clients to receive instant memory and room updates.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Dict, Set

logger = logging.getLogger("onecontext.broadcaster")


class Broadcaster:
    """Pub/Sub dispatcher keyed by room/project ID."""

    def __init__(self):
        self._listeners: Dict[str, Set[asyncio.Queue]] = {}

    def subscribe(self, channel_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        if channel_id not in self._listeners:
            self._listeners[channel_id] = set()
        self._listeners[channel_id].add(q)
        return q

    def unsubscribe(self, channel_id: str, q: asyncio.Queue) -> None:
        if channel_id in self._listeners:
            self._listeners[channel_id].discard(q)
            if not self._listeners[channel_id]:
                del self._listeners[channel_id]

    async def broadcast(self, channel_id: str, event_data: dict) -> None:
        listeners = self._listeners.get(channel_id, set())
        for q in list(listeners):
            await q.put(event_data)

    def publish_nowait(self, channel_id: str, event_data: dict) -> None:
        """Publish without requiring caller to await; schedules on active event loop."""
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.broadcast(channel_id, event_data))
        except RuntimeError:
            pass


broadcaster = Broadcaster()
