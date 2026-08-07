from limits.clock import ManualClock
from limits.window import SlidingWindow


def test_calls_expire_out_of_window():
    clock = ManualClock()
    w = SlidingWindow(limit=2, window=10, clock=clock)
    assert w.allow() is True
    assert w.allow() is True
    assert w.allow() is False
    clock.advance(10.1)
    assert w.allow() is True


def test_partial_expiry_frees_one_slot():
    clock = ManualClock()
    w = SlidingWindow(limit=2, window=10, clock=clock)
    assert w.allow() is True
    clock.advance(5)
    assert w.allow() is True
    assert w.allow() is False
    clock.advance(5.1)      # the first call has aged out, the second has not
    assert w.allow() is True
    assert w.allow() is False


def test_limit_of_one():
    clock = ManualClock()
    w = SlidingWindow(limit=1, window=5, clock=clock)
    assert w.allow() is True
    clock.advance(4.9)
    assert w.allow() is False
    clock.advance(0.2)
    assert w.allow() is True


def test_steady_state_rate_is_capped():
    clock = ManualClock()
    w = SlidingWindow(limit=3, window=10, clock=clock)
    allowed = 0
    for _ in range(100):
        if w.allow():
            allowed += 1
        clock.advance(1)
    # 100 seconds at 3 per rolling 10s is ~30 calls, never 2x that.
    assert 28 <= allowed <= 32
