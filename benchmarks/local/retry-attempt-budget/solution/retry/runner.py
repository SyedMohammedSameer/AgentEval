import time

from retry.policy import Policy


def call_with_retry(fn, policy: Policy | None = None):
    """Call `fn`, retrying on exception according to `policy`.

    Returns fn's result, or re-raises the final exception once attempts run out.
    """
    policy = policy or Policy()
    last_exc = None
    for attempt in range(policy.max_attempts):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if attempt < policy.max_attempts - 1:
                time.sleep(policy.delay_for(attempt))
    raise last_exc
