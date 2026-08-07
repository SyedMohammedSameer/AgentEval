import heapq
from itertools import count


class PriorityQueue:
    """Lowest priority value pops first; ties pop in insertion order."""

    def __init__(self):
        self._heap = []
        self._seq = count()

    def push(self, priority: int, item) -> None:
        # The monotonic counter breaks every tie before the payload is reached,
        # so heapq never needs the items to be orderable.
        heapq.heappush(self._heap, (priority, next(self._seq), item))

    def pop(self):
        if not self._heap:
            raise IndexError("pop from an empty queue")
        _priority, _seq, item = heapq.heappop(self._heap)
        return item

    def __len__(self) -> int:
        return len(self._heap)
