class ManualClock:
    """A hand-advanced clock so breaker timing is deterministic under test."""

    def __init__(self, now: float = 0.0):
        self._now = now

    def time(self) -> float:
        return self._now

    def advance(self, seconds: float) -> None:
        self._now += seconds
