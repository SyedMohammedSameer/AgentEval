import pytest

from retry.policy import Policy
from retry.runner import call_with_retry


def test_success_first_try_no_retry():
    calls = []

    def ok():
        calls.append(1)
        return "fine"

    assert call_with_retry(ok, Policy(max_attempts=3)) == "fine"
    assert len(calls) == 1


def test_succeeds_on_last_allowed_attempt():
    calls = []

    def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise ValueError("not yet")
        return "ok"

    assert call_with_retry(flaky, Policy(max_attempts=3)) == "ok"
    assert len(calls) == 3


def test_single_attempt_means_no_retry():
    calls = []

    def boom():
        calls.append(1)
        raise RuntimeError("x")

    with pytest.raises(RuntimeError):
        call_with_retry(boom, Policy(max_attempts=1))
    assert len(calls) == 1


def test_final_exception_propagates():
    def boom():
        raise KeyError("last")

    with pytest.raises(KeyError):
        call_with_retry(boom, Policy(max_attempts=2))


def test_delay_schedule_grows_then_caps():
    p = Policy(base_delay=0.01, factor=2.0, max_delay=0.05)
    assert p.delay_for(0) == pytest.approx(0.01)
    assert p.delay_for(1) == pytest.approx(0.02)
    assert p.delay_for(2) == pytest.approx(0.04)
    assert p.delay_for(3) == pytest.approx(0.05)
    assert p.delay_for(50) == pytest.approx(0.05)
