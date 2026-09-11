"""
通用内存事件总线
"""

import asyncio
from collections import defaultdict
from typing import Awaitable, Callable

from utils.domain_events import Event
from utils.log_util import logger

EventHandler = Callable[[Event], Awaitable[None]]


class InMemoryEventBus:
    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def subscribe(self, event_type: str, handler: EventHandler) -> None:
        async with self._lock:
            self._handlers[event_type].append(handler)

    async def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        async with self._lock:
            if handler in self._handlers[event_type]:
                self._handlers[event_type].remove(handler)

    async def publish(self, event: Event) -> None:
        handlers = list(self._handlers.get(event.type, [])) + list(self._handlers.get('*', []))
        if not handlers:
            return
        results = await asyncio.gather(
            *(self._safe_invoke(handler, event) for handler in handlers),
            return_exceptions=True,
        )
        for result in results:
            if isinstance(result, Exception):
                logger.warning(f'Event handler raised: {result}')

    @staticmethod
    async def _safe_invoke(handler: EventHandler, event: Event) -> None:
        try:
            await handler(event)
        except Exception as exc:
            logger.warning(f'Handler {getattr(handler, "__name__", handler)} failed: {exc}')


event_bus = InMemoryEventBus()
