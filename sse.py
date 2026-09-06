"""
SSE event stream — Owner: Hunar.

This is what makes re-planning VISIBLE on screen during the demo (Section 2.3 of the
orchestration doc), instead of only appearing in a console log. The admin panel's live
node-graph animation (Sher, frontend/app/admin) subscribes to GET /api/graph-events and
highlights whichever node/edge the latest event refers to.

Simple in-memory pub/sub — fine for a single-process hackathon demo. If you deploy the backend
with multiple workers, switch this to a Redis pub/sub channel instead (note left here so nobody
is surprised when events stop appearing after a Railway/Render restart with >1 worker).
"""
from __future__ import annotations

import asyncio
import json
from typing import Any

from sse_starlette.sse import EventSourceResponse

_subscribers: list[asyncio.Queue] = []


def publish_event(event: dict[str, Any]) -> None:
    for q in list(_subscribers):
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            pass


async def event_stream() -> EventSourceResponse:
    queue: asyncio.Queue = asyncio.Queue(maxsize=100)
    _subscribers.append(queue)

    async def generator():
        try:
            while True:
                event = await queue.get()
                yield {"event": event.get("type", "message"), "data": json.dumps(event)}
        finally:
            _subscribers.remove(queue)

    return EventSourceResponse(generator())
