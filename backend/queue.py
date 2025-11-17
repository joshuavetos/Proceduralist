"""Redis RQ integration with a deterministic fallback."""
from __future__ import annotations

import os
from typing import Any, Callable

import redis
from rq import Queue

from backend import auditor, clauses


class _SynchronousQueue:
    """Fallback queue that executes jobs immediately for offline runs."""

    def enqueue(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:  # type: ignore[override]
        return func(*args, **kwargs)

    def __len__(self) -> int:
        return 0

    def count(self) -> int:  # pragma: no cover - parity shim
        return 0


def get_queue() -> Queue | _SynchronousQueue:
    redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
    try:
        client = redis.Redis.from_url(redis_url)
        # Verify connectivity deterministically
        client.ping()
        return Queue(connection=client)
    except redis.RedisError:
        return _SynchronousQueue()


auditor_metadata = {"auditor": auditor, "clauses": clauses}
