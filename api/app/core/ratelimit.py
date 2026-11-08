"""In-memory sliding-window limit per key (the public link routes, D100).

The pilot runs one API process; with several processes each one keeps its own window, so the
effective limit multiplies by the number of processes. Nothing is stored: no IP reaches the
database or the logs.
"""

import time
from collections import deque

from fastapi import Request

MAX_KEYS = 10_000


class WindowLimiter:
    def __init__(self, limit: int, window_seconds: int) -> None:
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = {}

    def hit(self, key: str, now: float | None = None) -> bool:
        """Count one request; False when the key already used its limit in the window."""
        now = time.monotonic() if now is None else now
        if len(self._hits) > MAX_KEYS:
            self._prune(now)
        hits = self._hits.setdefault(key, deque())
        while hits and hits[0] <= now - self.window:
            hits.popleft()
        if len(hits) >= self.limit:
            return False
        hits.append(now)
        return True

    def _prune(self, now: float) -> None:
        for key in [k for k, v in self._hits.items() if not v or v[-1] <= now - self.window]:
            del self._hits[key]


def client_ip(request: Request) -> str:
    """The address the edge saw. The load balancer (and, without one, the web server) puts the
    client address in X-Forwarded-For; the last entry is the one added by our own edge, so a
    value forged by the client earlier in the list is ignored."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        last = forwarded.split(",")[-1].strip()
        if last:
            return last
    return request.client.host if request.client else "desconhecido"
