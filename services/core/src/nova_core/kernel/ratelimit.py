"""In-process token-bucket rate limiting."""

import math
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime

from fastapi import Request

from nova_core.kernel.clock import Clock
from nova_core.kernel.errors import NovaError


@dataclass(frozen=True)
class RateDecision:
    allowed: bool
    retry_after_seconds: int


class TokenBucketLimiter:
    """One bucket per key, kept in memory and bounded by ``max_keys``."""

    def __init__(
        self, capacity: int, refill_per_second: float, clock: Clock, *, max_keys: int = 10_000
    ) -> None:
        self._capacity = float(capacity)
        self._refill_per_second = refill_per_second
        self._clock = clock
        self._max_keys = max_keys
        self._buckets: dict[str, tuple[float, datetime]] = {}

    @property
    def tracked_keys(self) -> int:
        return len(self._buckets)

    def _tokens_at(self, tokens: float, updated: datetime, now: datetime) -> float:
        elapsed = (now - updated).total_seconds()
        return min(self._capacity, tokens + elapsed * self._refill_per_second)

    def _make_room(self, now: datetime) -> None:
        if len(self._buckets) < self._max_keys:
            return
        # A bucket that has refilled completely says nothing a new one would not.
        for key, (tokens, updated) in list(self._buckets.items()):
            if self._tokens_at(tokens, updated, now) >= self._capacity:
                del self._buckets[key]
        while len(self._buckets) >= self._max_keys:
            del self._buckets[min(self._buckets, key=lambda key: self._buckets[key][1])]

    def check(self, key: str) -> RateDecision:
        now = self._clock.now()
        if key not in self._buckets:
            self._make_room(now)
        tokens, updated = self._buckets.get(key, (self._capacity, now))
        tokens = self._tokens_at(tokens, updated, now)
        if tokens >= 1:
            self._buckets[key] = (tokens - 1, now)
            return RateDecision(allowed=True, retry_after_seconds=0)
        self._buckets[key] = (tokens, now)
        wait = (1 - tokens) / self._refill_per_second
        return RateDecision(allowed=False, retry_after_seconds=max(1, math.ceil(wait - 1e-9)))


def rate_limit(name: str) -> Callable[[Request], Awaitable[None]]:
    """FastAPI dependency: applies the limiter registered under ``name``, per client address.

    The address is the peer of the connection. The server runs with proxy headers off
    (see ``nova_core.__main__.server_options``), so a client cannot choose it.
    """

    async def dependency(request: Request) -> None:
        limiter: TokenBucketLimiter = request.app.state.rate_limiters[name]
        client = request.client.host if request.client else "unknown"
        decision = limiter.check(f"{name}:{client}")
        if not decision.allowed:
            raise NovaError(
                "rate_limited",
                429,
                "Too many attempts. Try again later.",
                headers={"Retry-After": str(decision.retry_after_seconds)},
            )

    return dependency
