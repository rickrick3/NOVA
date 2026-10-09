from datetime import timedelta

from nova_core.kernel.ratelimit import TokenBucketLimiter
from tests.support import FakeClock


def test_bucket_allows_capacity_then_denies_then_refills():
    clock = FakeClock()
    limiter = TokenBucketLimiter(capacity=2, refill_per_second=1.0, clock=clock)
    assert limiter.check("k").allowed and limiter.check("k").allowed
    denied = limiter.check("k")
    assert (denied.allowed, denied.retry_after_seconds) == (False, 1)
    clock.advance(timedelta(seconds=1))
    assert limiter.check("k").allowed


def test_keys_are_independent():
    limiter = TokenBucketLimiter(capacity=1, refill_per_second=1.0, clock=FakeClock())
    assert limiter.check("a").allowed
    assert limiter.check("b").allowed
    assert not limiter.check("a").allowed
