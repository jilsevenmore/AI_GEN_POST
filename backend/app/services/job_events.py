"""In-memory pub/sub for real-time job progress updates over WebSocket."""
import asyncio
from collections import defaultdict
from typing import Any, Dict, Set

_subscribers: Dict[str, Set[asyncio.Queue]] = defaultdict(set)


def subscribe_job(job_id: str) -> asyncio.Queue:
    """Subscribe to progress events for a job."""
    queue: asyncio.Queue = asyncio.Queue(maxsize=32)
    _subscribers[str(job_id)].add(queue)
    return queue


def unsubscribe_job(job_id: str, queue: asyncio.Queue) -> None:
    """Unsubscribe a queue from a job's progress events."""
    key = str(job_id)
    subs = _subscribers.get(key)
    if not subs:
        return
    subs.discard(queue)
    if not subs:
        _subscribers.pop(key, None)


def publish_job_event(job_id: str, payload: Dict[str, Any]) -> None:
    """Publish a job progress update to all active WebSocket subscribers."""
    subs = _subscribers.get(str(job_id))
    if not subs:
        return
    for queue in list(subs):
        if queue.full():
            try:
                queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
        try:
            queue.put_nowait(payload)
        except asyncio.QueueFull:
            pass
