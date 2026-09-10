"""
SSE event stream — Owner: Hunar.

Fix applied: publish_event() can be called from a background thread (FastAPI runs regular
`def` endpoints off the main event loop). asyncio.Queue isn't safe to write to directly from
another thread, so we route through call_soon_threadsafe once we know the running loop.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any

from sse_starlette.sse import EventSourceResponse

_subscribers: list[asyncio.Queue] = []
_loop: asyncio.AbstractEventLoop | None = None


def _safe_put(q: asyncio.Queue, event: dict) -> None:
    try:
        q.put_nowait(event)
    except asyncio.QueueFull:
        pass


def publish_event(event: dict[str, Any]) -> None:
    for q in list(_subscribers):
        if _loop is not None:
            _loop.call_soon_threadsafe(_safe_put, q, event)
        else:
            _safe_put(q, event)


async def event_stream() -> EventSourceResponse:
    global _loop
    _loop = asyncio.get_running_loop()

    queue: asyncio.Queue = asyncio.Queue(maxsize=100)
    _subscribers.append(queue)

    async def generator():
        try:
            while True:
                event = await queue.get()
                yield {"data": json.dumps(event)}
        finally:
            _subscribers.remove(queue)

    return EventSourceResponse(generator())