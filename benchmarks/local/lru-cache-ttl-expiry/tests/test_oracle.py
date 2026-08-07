from cache.clock import ManualClock
from cache.store import TTLCache


def test_expiry_boundary_is_exclusive():
    clock = ManualClock()
    c = TTLCache(capacity=4, ttl=10, clock=clock)
    c.set("a", 1)
    clock.advance(10)
    # Exactly at the TTL the entry is still considered fresh.
    assert c.get("a") == 1
    clock.advance(0.001)
    assert c.get("a") is None


def test_expired_entry_respects_default():
    clock = ManualClock()
    c = TTLCache(capacity=2, ttl=5, clock=clock)
    c.set("a", 1)
    clock.advance(6)
    assert c.get("a", "gone") == "gone"


def test_read_refreshes_recency():
    c = TTLCache(capacity=2, ttl=100, clock=ManualClock())
    c.set("a", 1)
    c.set("b", 2)
    c.get("a")          # "a" is now the most recently used
    c.set("c", 3)       # evicts the least recently used, which is "b"
    assert c.get("a") == 1
    assert c.get("b") is None
    assert c.get("c") == 3


def test_capacity_enforced():
    c = TTLCache(capacity=2, ttl=100, clock=ManualClock())
    for k in "abc":
        c.set(k, k)
    assert len(c) == 2


def test_overwrite_refreshes_timestamp():
    clock = ManualClock()
    c = TTLCache(capacity=2, ttl=10, clock=clock)
    c.set("a", 1)
    clock.advance(8)
    c.set("a", 2)
    clock.advance(5)
    assert c.get("a") == 2
