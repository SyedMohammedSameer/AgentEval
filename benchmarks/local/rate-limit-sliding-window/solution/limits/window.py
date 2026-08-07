from collections import deque

from limits.clock import ManualClock


class SlidingWindow:
    def __init__(self, limit: int, window: float, clock=None):
        self.limit = limit
        self.window = window
        self.clock = clock or ManualClock()
        self._calls: deque = deque()

    def allow(self) -> bool:
        """Return True if a call is permitted now, recording it if so."""
        now = self.clock.time()
        cutoff = now - self.window
        while self._calls and self._calls[0] <= cutoff:
            self._calls.popleft()
        if len(self._calls) < self.limit:
            self._calls.append(now)
            return True
        return False
