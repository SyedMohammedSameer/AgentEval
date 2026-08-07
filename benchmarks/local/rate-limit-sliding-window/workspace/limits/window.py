from limits.clock import ManualClock


class SlidingWindow:
    def __init__(self, limit: int, window: float, clock=None):
        self.limit = limit
        self.window = window
        self.clock = clock or ManualClock()
        self._count = 0
        self._bucket_start = self.clock.time()

    def allow(self) -> bool:
        """Return True if a call is permitted now, recording it if so."""
        now = self.clock.time()
        # BUG: this is a fixed window. The counter resets wholesale once the
        # bucket elapses, so `limit` calls at the end of one bucket plus `limit`
        # at the start of the next both succeed - 2x the intended rate.
        if now - self._bucket_start >= self.window:
            self._bucket_start = now
            self._count = 0
        if self._count < self.limit:
            self._count += 1
            return True
        return False
