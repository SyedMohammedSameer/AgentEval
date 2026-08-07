from batch.clock import ManualClock


class Batcher:
    def __init__(self, sink, max_size: int = 3, max_age: float = 5.0, clock=None):
        self.sink = sink
        self.max_size = max_size
        self.max_age = max_age
        self.clock = clock or ManualClock()
        self._items: list = []
        # Timestamp of the batch's *first* item, so age reflects how long the
        # oldest item has waited rather than how recently one arrived.
        self._batch_started = None

    def add(self, item) -> None:
        if not self._items:
            self._batch_started = self.clock.time()
        self._items.append(item)
        if len(self._items) >= self.max_size:
            self.flush()

    def tick(self) -> None:
        """Give the batcher a chance to flush on age alone."""
        if self._items and self.clock.time() - self._batch_started >= self.max_age:
            self.flush()

    def flush(self) -> None:
        if not self._items:
            return
        self.sink(list(self._items))
        self._items.clear()
        self._batch_started = None

    def close(self) -> None:
        self.flush()
