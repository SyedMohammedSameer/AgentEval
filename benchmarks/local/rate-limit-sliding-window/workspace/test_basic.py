from limits.clock import ManualClock
from limits.window import SlidingWindow


def test_allows_up_to_limit():
    w = SlidingWindow(limit=2, window=10, clock=ManualClock())
    assert w.allow() is True
    assert w.allow() is True
    assert w.allow() is False


def test_no_double_rate_across_boundary():
    clock = ManualClock()
    w = SlidingWindow(limit=2, window=10, clock=clock)
    clock.advance(9)
    assert w.allow() is True
    assert w.allow() is True
    clock.advance(1.5)   # old calls are still within the rolling 10s window
    assert w.allow() is False
