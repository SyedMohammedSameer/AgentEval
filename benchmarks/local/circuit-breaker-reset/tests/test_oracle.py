import pytest

from breaker.circuit import CLOSED, OPEN, CircuitBreaker, CircuitOpen
from breaker.clock import ManualClock


def _boom():
    raise RuntimeError("x")


def test_open_circuit_rejects_without_calling():
    b = CircuitBreaker(threshold=1, reset_after=10, clock=ManualClock())
    with pytest.raises(RuntimeError):
        b.call(_boom)
    with pytest.raises(CircuitOpen):
        b.call(lambda: "ok")


def test_successful_half_open_trial_closes_the_circuit():
    clock = ManualClock()
    b = CircuitBreaker(threshold=1, reset_after=10, clock=clock)
    with pytest.raises(RuntimeError):
        b.call(_boom)
    clock.advance(10)
    assert b.call(lambda: "ok") == "ok"
    assert b.state == CLOSED


def test_failed_half_open_trial_reopens():
    clock = ManualClock()
    b = CircuitBreaker(threshold=1, reset_after=10, clock=clock)
    with pytest.raises(RuntimeError):
        b.call(_boom)
    clock.advance(10)
    with pytest.raises(RuntimeError):
        b.call(_boom)
    assert b.state == OPEN


def test_failure_count_returns_to_zero_on_success():
    b = CircuitBreaker(threshold=3, clock=ManualClock())
    for _ in range(2):
        with pytest.raises(RuntimeError):
            b.call(_boom)
    b.call(lambda: "ok")
    assert b.failures == 0


def test_still_open_before_the_reset_window():
    clock = ManualClock()
    b = CircuitBreaker(threshold=1, reset_after=10, clock=clock)
    with pytest.raises(RuntimeError):
        b.call(_boom)
    clock.advance(9)
    with pytest.raises(CircuitOpen):
        b.call(lambda: "ok")


def test_closed_circuit_passes_the_result_through():
    assert CircuitBreaker(clock=ManualClock()).call(lambda: 42) == 42
