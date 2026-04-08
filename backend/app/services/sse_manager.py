"""SSE connection manager — in-memory queue dict for Call Intelligence events.

Each tenant+user gets its own asyncio.Queue. The webhook handler pushes events,
and the SSE endpoint streams them to the connected frontend.
"""

import asyncio
import logging
from collections import defaultdict
from typing import Any

logger = logging.getLogger(__name__)

# Key: (tenant_id, user_id) → list of queues (one user could have multiple tabs)
_connections: dict[tuple[str, str], list[asyncio.Queue]] = defaultdict(list)


def subscribe(tenant_id: str, user_id: str) -> asyncio.Queue:
    """Register a new SSE connection. Returns the queue to consume from."""
    queue: asyncio.Queue = asyncio.Queue()
    _connections[(tenant_id, user_id)].append(queue)
    logger.debug("SSE subscribe: tenant=%s user=%s (total=%d)", tenant_id, user_id, len(_connections[(tenant_id, user_id)]))
    return queue


def unsubscribe(tenant_id: str, user_id: str, queue: asyncio.Queue) -> None:
    """Remove a disconnected SSE connection."""
    key = (tenant_id, user_id)
    if key in _connections:
        try:
            _connections[key].remove(queue)
        except ValueError:
            pass
        if not _connections[key]:
            del _connections[key]
    logger.debug("SSE unsubscribe: tenant=%s user=%s", tenant_id, user_id)


def emit_to_tenant(tenant_id: str, event: str, data: dict[str, Any]) -> int:
    """Push an event to ALL users connected for a given tenant.

    Returns the number of queues that received the event.
    """
    count = 0
    for (tid, _uid), queues in list(_connections.items()):
        if tid != tenant_id:
            continue
        for q in queues:
            try:
                q.put_nowait({"event": event, "data": data})
                count += 1
            except asyncio.QueueFull:
                logger.warning("SSE queue full for tenant=%s user=%s — dropping event", tid, _uid)
    return count


def emit_to_user(tenant_id: str, user_id: str, event: str, data: dict[str, Any]) -> int:
    """Push an event to a specific user in a tenant."""
    key = (tenant_id, user_id)
    queues = _connections.get(key, [])
    count = 0
    for q in queues:
        try:
            q.put_nowait({"event": event, "data": data})
            count += 1
        except asyncio.QueueFull:
            logger.warning("SSE queue full for user=%s", user_id)
    return count


def get_connection_count(tenant_id: str | None = None) -> int:
    """Return total active SSE connections, optionally filtered by tenant."""
    if tenant_id:
        return sum(len(qs) for (tid, _), qs in _connections.items() if tid == tenant_id)
    return sum(len(qs) for qs in _connections.values())
