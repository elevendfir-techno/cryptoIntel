"""
CryptoIntel Real-Time Event Bus

Receives normalized events and distributes them
to subscribers such as:

- Database writer
- Detection engine
- Risk engine
- Fund-flow engine
- Alert engine
- Evidence engine
"""

from __future__ import annotations

import asyncio
import inspect
import logging
from typing import Any, Awaitable, Callable


logger = logging.getLogger("cryptointel.event_bus")


EventHandler = Callable[
    [dict[str, Any]],
    Awaitable[None] | None
]


class EventBus:

    def __init__(self) -> None:
        self._subscribers: list[EventHandler] = []

        self.events_published = 0
        self.events_delivered = 0
        self.delivery_failures = 0

    def subscribe(
        self,
        handler: EventHandler,
    ) -> None:
        """Register an event consumer."""

        if handler not in self._subscribers:
            self._subscribers.append(handler)

            logger.info(
                "Event subscriber registered: %s",
                getattr(
                    handler,
                    "__name__",
                    repr(handler)
                )
            )

    def unsubscribe(
        self,
        handler: EventHandler,
    ) -> None:
        """Remove an event consumer."""

        if handler in self._subscribers:
            self._subscribers.remove(handler)

    async def publish(
        self,
        event: dict[str, Any],
    ) -> None:
        """
        Publish one normalized event to every subscriber.
        """

        self.events_published += 1

        if not self._subscribers:
            return

        results = await asyncio.gather(
            *[
                self._deliver(
                    handler,
                    event
                )
                for handler in list(
                    self._subscribers
                )
            ],
            return_exceptions=True,
        )

        for result in results:
            if isinstance(
                result,
                Exception
            ):
                self.delivery_failures += 1

    async def _deliver(
        self,
        handler: EventHandler,
        event: dict[str, Any],
    ) -> None:

        try:
            result = handler(event)

            if inspect.isawaitable(result):
                await result

            self.events_delivered += 1

        except Exception:
            logger.exception(
                "Event subscriber failed: %s",
                getattr(
                    handler,
                    "__name__",
                    repr(handler)
                )
            )

            raise

    def subscriber_count(self) -> int:
        return len(
            self._subscribers
        )

    def health(self) -> dict[str, Any]:
        return {
            "status": "RUNNING",
            "subscribers": self.subscriber_count(),
            "events_published": (
                self.events_published
            ),
            "events_delivered": (
                self.events_delivered
            ),
            "delivery_failures": (
                self.delivery_failures
            ),
        }


# Shared event bus instance.
event_bus = EventBus()