"""An in-process event bus: what happened in the assistant, for whatever wants to know.

Each part that reacts to the assistant's activity (the local API's live
view, a channel that reports a finished task, the web page) used to need
a hook into the code that did the work. The orchestrator now publishes
named events instead, and each consumer subscribes to the topics it
needs:

    turn.finished   a turn ended: what was heard, said, its status
    task.ran        a scheduled check or action ran
    tool.called     a tool call finished (server, tool, status)
    message.in      a message arrived on a channel

publish() never waits for a subscriber and never raises: each subscriber
has its own bounded queue, drained by its own task, and a subscriber that
falls behind loses its oldest events (counted in dropped) rather than
slowing a voice turn. A subscriber that raises is logged and keeps
receiving.
"""

from __future__ import annotations

import asyncio
import contextlib
import fnmatch
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

#: Events a subscriber may fall behind by before the oldest are dropped.
QUEUE_SIZE = 200

Handler = Callable[["Event"], Awaitable[None] | None]


@dataclass(frozen=True, slots=True)
class Event:
    topic: str
    data: dict[str, Any]
    at: float = field(default_factory=time.time)


class _Subscription:
    def __init__(self, pattern: str, handler: Handler) -> None:
        self.pattern = pattern
        self.handler = handler
        self.queue: asyncio.Queue[Event] = asyncio.Queue(QUEUE_SIZE)
        self.dropped = 0
        self.task: asyncio.Task[None] | None = None

    async def drain(self) -> None:
        while True:
            event = await self.queue.get()
            try:
                result = self.handler(event)
                if asyncio.iscoroutine(result):
                    await result
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Event subscriber for %s failed on %s", self.pattern, event.topic)


class EventBus:
    """Topics matched by glob ("turn.*", "*"); one queue and task per subscriber."""

    def __init__(self) -> None:
        self._subs: list[_Subscription] = []

    def subscribe(self, pattern: str, handler: Handler) -> Callable[[], None]:
        """Call *handler* for every event whose topic matches *pattern*; returns a function that unsubscribes."""
        sub = _Subscription(pattern, handler)
        self._subs.append(sub)

        def unsubscribe() -> None:
            if sub in self._subs:
                self._subs.remove(sub)
            if sub.task is not None:
                sub.task.cancel()

        return unsubscribe

    def publish(self, topic: str, **data: Any) -> None:
        """Hand *topic* with *data* to every matching subscriber; never blocks, never raises."""
        event = Event(topic=topic, data=data)
        for sub in list(self._subs):
            if not fnmatch.fnmatchcase(topic, sub.pattern):
                continue
            try:
                if sub.task is None or sub.task.done():
                    sub.task = asyncio.get_running_loop().create_task(sub.drain())
            except RuntimeError:
                return  # no running loop: nothing could deliver it
            if sub.queue.full():
                with contextlib.suppress(asyncio.QueueEmpty):
                    sub.queue.get_nowait()
                sub.dropped += 1
            sub.queue.put_nowait(event)

    def stream(self, pattern: str = "*") -> tuple[asyncio.Queue[Event], Callable[[], None]]:
        """A queue that receives matching events, for a consumer that reads at its own pace (the API's live view)."""
        queue: asyncio.Queue[Event] = asyncio.Queue(QUEUE_SIZE)

        def put(event: Event) -> None:
            if queue.full():
                with contextlib.suppress(asyncio.QueueEmpty):
                    queue.get_nowait()
            queue.put_nowait(event)

        return queue, self.subscribe(pattern, put)

    async def close(self) -> None:
        tasks = [s.task for s in self._subs if s.task is not None]
        self._subs.clear()
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
