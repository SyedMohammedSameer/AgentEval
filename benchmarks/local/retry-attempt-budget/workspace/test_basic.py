from retry.policy import Policy
from retry.runner import call_with_retry


def test_attempt_count():
    calls = []

    def boom():
        calls.append(1)
        raise ValueError("nope")

    try:
        call_with_retry(boom, Policy(max_attempts=3))
    except ValueError:
        pass
    assert len(calls) == 3


def test_delay_capped():
    p = Policy(base_delay=0.01, factor=2.0, max_delay=0.05)
    assert p.delay_for(10) == 0.05
