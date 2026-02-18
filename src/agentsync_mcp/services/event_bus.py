from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Callable, Coroutine

logger = logging.getLogger(__name__)

Listener = Callable[[dict[str, Any]], Coroutine[Any, Any, None]]


class EventBus:
    """Simple async pub/sub event bus for real-time notifications.

    Agents can subscribe to specific event types (or "*" for all events)
    and receive dicts with event data whenever something happens.
    """

    def __init__(self) -> None:
        self._listeners: dict[str, list[Listener]] = {}

    def subscribe(self, event_type: str, listener: Listener) -> None:
        self._listeners.setdefault(event_type, []).append(listener)

    def unsubscribe(self, event_type: str, listener: Listener) -> None:
        listeners = self._listeners.get(event_type, [])
        if listener in listeners:
            listeners.remove(listener)

    async def publish(self, event_type: str, data: dict[str, Any]) -> None:
        """Fire an event to all matching listeners."""
        event = {
            "type": event_type,
            "timestamp": datetime.now().isoformat(),
            **data,
        }

        targets: list[Listener] = []
        targets.extend(self._listeners.get(event_type, []))
        targets.extend(self._listeners.get("*", []))

        if not targets:
            return

        results = await asyncio.gather(
            *(listener(event) for listener in targets),
            return_exceptions=True,
        )
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error("Event listener error for %s: %s", event_type, result)
