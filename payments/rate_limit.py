"""A small in-memory rate limiter for the two endpoints the app calls directly.

Deliberately not applied to the webhook. Stripe decides when to send events, a
429 there only turns into a retry, and delaying an unlock in order to slow
Stripe down is the wrong trade every time. It is not applied to the success and
cancel redirects either, since those are a customer coming back from a payment
they have already made.

Limits are per client address and deliberately generous. Mobile users sit
behind carrier NAT, so a whole city can share one address, and a tight limit
would lock out paying customers long before it inconvenienced anyone abusive.

State lives in this process. PythonAnywhere serves this app from a single
worker, so the count is accurate there. Run it with several workers, or across
more than one machine, and each keeps its own tally, so the effective limit
multiplies by the number of processes. That is the point at which this should
move to Redis rather than being tuned.
"""

import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import HTTPException, Request

from payments.config import settings
from payments.logging_config import fields, get_logger

logger = get_logger("rate_limit")

FORWARDED_FOR_HEADER = "x-forwarded-for"
UNKNOWN_CLIENT = "unknown"
TOO_MANY_REQUESTS = 429

# Callers idle for longer than this are forgotten, so the table cannot grow
# without bound on a process that stays up for weeks.
IDLE_CALLER_TTL_SECONDS = 3600


def client_key(request: Request) -> str:
    """Work out who is calling.

    PythonAnywhere puts a proxy in front of the app, so `request.client.host`
    is the proxy rather than the customer, and every caller would share one
    bucket. The first entry of X-Forwarded-For is the original client.

    That header is only worth trusting because a proxy we do not control sets
    it. On a host without one it can be forged, and the limiter becomes
    bypassable. It is a speed bump against accidental hammering, not a defence
    against someone determined.
    """
    forwarded = request.headers.get(FORWARDED_FOR_HEADER)
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return UNKNOWN_CLIENT


class SlidingWindowLimiter:
    """Allows `limit` requests per `window_seconds` for each caller.

    Keeps the timestamps of recent requests rather than a plain counter, so the
    window slides instead of resetting on a fixed boundary. A fixed window lets
    a caller send double the limit by straddling the reset.
    """

    def __init__(self, limit: int, window_seconds: int) -> None:
        self._limit = limit
        self._window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()
        self._last_swept = 0.0

    def check(self, key: str) -> float | None:
        """Record a request. Returns seconds to wait, or None if allowed."""
        now = time.monotonic()
        with self._lock:
            self._forget_idle_callers(now)
            hits = self._hits[key]
            while hits and now - hits[0] >= self._window:
                hits.popleft()
            if len(hits) >= self._limit:
                return self._window - (now - hits[0])
            hits.append(now)
            return None

    def _forget_idle_callers(self, now: float) -> None:
        if now - self._last_swept < IDLE_CALLER_TTL_SECONDS:
            return
        self._last_swept = now
        idle = [
            key
            for key, hits in self._hits.items()
            if not hits or now - hits[-1] > IDLE_CALLER_TTL_SECONDS
        ]
        for key in idle:
            del self._hits[key]


_limiter = SlidingWindowLimiter(
    settings.rate_limit_requests,
    settings.rate_limit_window_seconds,
)


def rate_limit(request: Request) -> None:
    """FastAPI dependency. Raises 429 when a caller is over the limit."""
    if not settings.rate_limit_enabled:
        return

    key = client_key(request)
    retry_after = _limiter.check(key)
    if retry_after is None:
        return

    logger.warning("rate limited %s", fields(client=key, path=request.url.path))
    raise HTTPException(
        status_code=TOO_MANY_REQUESTS,
        detail="Too many requests. Try again shortly.",
        headers={"Retry-After": str(max(1, int(retry_after) + 1))},
    )
