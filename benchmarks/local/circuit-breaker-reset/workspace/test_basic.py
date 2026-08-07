import pytest

from breaker.circuit import CLOSED, OPEN, CircuitBreaker
from breaker.clock import ManualClock


def _boom():
    raise RuntimeError("x")


def test_opens_after_threshold_failures():
    b = CircuitBreaker(threshold=2, clock=ManualClock())
    for _ in range(2):
        with pytest.raises(RuntimeError):
            b.call(_boom)
    assert b.state == OPEN


def test_success_clears_the_failure_count():
    b = CircuitBreaker(threshold=2, clock=ManualClock())
    with pytest.raises(RuntimeError):
        b.call(_boom)
    b.call(lambda: "ok")
    with pytest.raises(RuntimeError):
        b.call(_boom)
    assert b.state == CLOSED
