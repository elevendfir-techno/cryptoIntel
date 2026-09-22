"""
CryptoIntel Global Real-Time Data Engine

Purpose:
- Receive real-time events from existing collectors.
- Normalize events.
- Publish normalized events to the event bus.
- Keep the engine independent from existing API routes.

No fake/demo/random data is generated here.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from .event_bus import EventBus
from .normalization import normalize_event

logger = logging.getLogger("cryptointel.data_engine")


EventHandler = Callable[[dict[str, Any]], Awaitable[None] | None]


class DataEngine:
    """
    Central ingestion engine for CryptoIntel.

    Flow:

        Collector
            ↓
        ingest()
            ↓
        normalize_event()
            ↓
        EventBus
            ↓
        subscribers
    """

    def __init__(self, event_bus: EventBus | None = None) -> None:
        self.event_bus = event_bus or EventBus()

        self._running = False
        self._tasks: set[asyncio.Task[Any]] = set()

        self.events_received = 0
        self.events_published = 0
        self.events_failed = 0

        self.started_at: str | None = None
        self.last_event_at: str | None = None

    async def start(self) -> None:
        """Start the data engine."""
        if self._running:
            logger.info("Data engine is already running.")
            return

        self._running = True
        self.started_at = self._utc_now()

        logger.info("CryptoIntel Global Data Engine started.")

    async def stop(self) -> None:
        """Stop the data engine and wait for background tasks."""
        if not self._running:
            return

        self._running = False

        if self._tasks:
            for task in self._tasks:
                task.cancel()

            await asyncio.gather(
                *self._tasks,
                return_exceptions=True
            )

            self._tasks.clear()

        logger.info("CryptoIntel Global Data Engine stopped.")

    async def ingest(
        self,
        event: dict[str, Any],
        source: str | None = None,
    ) -> dict[str, Any]:
        """
        Receive one real event from a collector.

        The event is normalized before being published.
        """

        if not self._running:
            raise RuntimeError(
                "Data engine is not running."
            )

        self.events_received += 1

        try:
            normalized = normalize_event(
                event,
                source=source
            )

            self.last_event_at = normalized["timestamp"]

            await self.event_bus.publish(normalized)

            self.events_published += 1

            return normalized

        except Exception:
            self.events_failed += 1

            logger.exception(
                "Failed to ingest event."
            )

            raise

    def submit(
        self,
        event: dict[str, Any],
        source: str | None = None,
    ) -> asyncio.Task[Any]:
        """
        Schedule ingestion without blocking the collector.

        Useful for high-frequency WebSocket collectors.
        """

        task = asyncio.create_task(
            self.ingest(
                event,
                source=source
            )
        )

        self._tasks.add(task)

        task.add_done_callback(
            self._tasks.discard
        )

        return task

    def subscribe(
        self,
        handler: EventHandler,
    ) -> None:
        """Subscribe a consumer to normalized events."""
        self.event_bus.subscribe(handler)

    def unsubscribe(
        self,
        handler: EventHandler,
    ) -> None:
        """Remove a consumer."""
        self.event_bus.unsubscribe(handler)

    def health(self) -> dict[str, Any]:
        """Return current data-engine health information."""

        return {
            "status": (
                "RUNNING"
                if self._running
                else "STOPPED"
            ),
            "started_at": self.started_at,
            "last_event_at": self.last_event_at,
            "events_received": self.events_received,
            "events_published": self.events_published,
            "events_failed": self.events_failed,
            "subscribers": self.event_bus.subscriber_count(),
        }

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(
            timezone.utc
        ).isoformat()


# Shared engine instance.
#
# Existing application code can later import this instance
# instead of creating multiple event engines.
data_engine = DataEngine()