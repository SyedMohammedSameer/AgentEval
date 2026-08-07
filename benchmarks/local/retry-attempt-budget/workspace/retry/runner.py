import time

from retry.policy import Policy


def call_with_retry(fn, policy: Policy | None = None):
    """Call `fn`, retrying on exception according to `policy`.

    Returns fn's result, or re-raises the final exception once attempts run out.
    """
    policy = policy or Policy()
    last_exc = None
    # BUG: range(max_attempts + 1) runs one extra attempt.
    for attempt in range(policy.max_attempts + 1):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            time.sleep(policy.delay_for(attempt))
    raise last_exc
