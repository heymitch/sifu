"""Watch the library dir; expose an SSE stream the timeline subscribes to."""

import asyncio, json
from sifu import library

_subscribers: list[asyncio.Queue] = []


async def event_stream():
    q: asyncio.Queue = asyncio.Queue()
    _subscribers.append(q)
    try:
        while True:
            msg = await q.get()
            yield f"data: {json.dumps(msg)}\n\n"
    finally:
        _subscribers.remove(q)


def notify(workflow_id: str):
    for q in list(_subscribers):
        q.put_nowait({"type": "new", "id": workflow_id})
