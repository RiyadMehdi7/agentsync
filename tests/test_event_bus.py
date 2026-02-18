from __future__ import annotations

import pytest

from agentsync_mcp.services.event_bus import EventBus


@pytest.mark.asyncio
class TestEventBus:
    async def test_subscribe_and_publish(self, event_bus: EventBus) -> None:
        received: list[dict] = []

        async def listener(event: dict) -> None:
            received.append(event)

        event_bus.subscribe("lock_acquired", listener)
        await event_bus.publish("lock_acquired", {"file": "a.py"})

        assert len(received) == 1
        assert received[0]["type"] == "lock_acquired"
        assert received[0]["file"] == "a.py"

    async def test_wildcard_subscription(self, event_bus: EventBus) -> None:
        received: list[dict] = []

        async def listener(event: dict) -> None:
            received.append(event)

        event_bus.subscribe("*", listener)

        await event_bus.publish("lock_acquired", {"file": "a.py"})
        await event_bus.publish("lock_released", {"file": "b.py"})

        assert len(received) == 2

    async def test_unsubscribe(self, event_bus: EventBus) -> None:
        received: list[dict] = []

        async def listener(event: dict) -> None:
            received.append(event)

        event_bus.subscribe("test", listener)
        await event_bus.publish("test", {"n": 1})
        assert len(received) == 1

        event_bus.unsubscribe("test", listener)
        await event_bus.publish("test", {"n": 2})
        assert len(received) == 1  # no new events

    async def test_no_listeners(self, event_bus: EventBus) -> None:
        # Should not raise
        await event_bus.publish("unheard_event", {"data": "ignored"})

    async def test_listener_error_does_not_break_others(self, event_bus: EventBus) -> None:
        received: list[dict] = []

        async def bad_listener(event: dict) -> None:
            raise RuntimeError("boom")

        async def good_listener(event: dict) -> None:
            received.append(event)

        event_bus.subscribe("test", bad_listener)
        event_bus.subscribe("test", good_listener)

        await event_bus.publish("test", {"data": "ok"})
        assert len(received) == 1
