from cache.clock import ManualClock
from cache.store import TTLCache


def test_hit_before_expiry():
    c = TTLCache(capacity=2, ttl=10, clock=ManualClock())
    c.set("a", 1)
    assert c.get("a") == 1


def test_expired_entry_is_a_miss():
    clock = ManualClock()
    c = TTLCache(capacity=2, ttl=10, clock=clock)
    c.set("a", 1)
    clock.advance(11)
    assert c.get("a") is None
