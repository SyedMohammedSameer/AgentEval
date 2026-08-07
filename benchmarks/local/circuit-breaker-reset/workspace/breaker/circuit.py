from breaker.clock import ManualClock

CLOSED, OPEN, HALF_OPEN = "closed", "open", "half_open"


class CircuitOpen(Exception):
    """The circuit is open and the call was not attempted."""


class CircuitBreaker:
    def __init__(self, threshold: int = 3, reset_after: float = 10.0, clock=None):
        self.threshold = threshold
        self.reset_after = reset_after
        self.clock = clock or ManualClock()
        self.state = CLOSED
        self.failures = 0
        self._opened_at = None

    def call(self, fn):
        if self.state == OPEN:
            if self.clock.time() - self._opened_at >= self.reset_after:
                self.state = HALF_OPEN
            else:
                raise CircuitOpen("circuit is open")
        try:
            result = fn()
        except Exception:
            self.failures += 1
            if self.failures >= self.threshold:
                self.state = OPEN
                self._opened_at = self.clock.time()
            raise
        # BUG: a success neither clears the failure counter - making the count
        # cumulative instead of consecutive - nor closes a half-open breaker,
        # which then stays half-open forever.
        return result
