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
    """One bucket per key. Buckets live in memory: enough for a single local user."""

    def __init__(self, capacity: int, refill_per_second: float, clock: Clock) -> None:
        self._capacity = float(capacity)
        self._refill_per_second = refill_per_second
        self._clock = clock
        self._buckets: dict[str, tuple[float, datetime]] = {}

    def check(self, key: str) -> RateDecision:
        now = self._clock.now()
        tokens, updated = self._buckets.get(key, (self._capacity, now))
        elapsed = (now - updated).total_seconds()
        tokens = min(self._capacity, tokens + elapsed * self._refill_per_second)
        if tokens >= 1:
            self._buckets[key] = (tokens - 1, now)
            return RateDecision(allowed=True, retry_after_seconds=0)
        self._buckets[key] = (tokens, now)
        wait = (1 - tokens) / self._refill_per_second
        return RateDecision(allowed=False, retry_after_seconds=max(1, math.ceil(wait - 1e-9)))


def rate_limit(name: str) -> Callable[[Request], Awaitable[None]]:
    """FastAPI dependency: applies the limiter registered under ``name``, per client address."""

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
