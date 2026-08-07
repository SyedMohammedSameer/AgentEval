from batch.clock import ManualClock


class Batcher:
    def __init__(self, sink, max_size: int = 3, max_age: float = 5.0, clock=None):
        self.sink = sink
        self.max_size = max_size
        self.max_age = max_age
        self.clock = clock or ManualClock()
        self._items: list = []
        self._last_add = self.clock.time()

    def add(self, item) -> None:
        self._items.append(item)
        # BUG: the age reference resets on every add, so a slow but steady
        # stream never reaches max_age and the batch is never time-flushed.
        self._last_add = self.clock.time()
        if len(self._items) >= self.max_size:
            self.flush()

    def tick(self) -> None:
        """Give the batcher a chance to flush on age alone."""
        if self._items and self.clock.time() - self._last_add >= self.max_age:
            self.flush()

    def flush(self) -> None:
        if not self._items:
            return
        self.sink(list(self._items))
        self._items.clear()

    def close(self) -> None:
        # BUG: pending items are dropped on close instead of being flushed.
        self._items.clear()
