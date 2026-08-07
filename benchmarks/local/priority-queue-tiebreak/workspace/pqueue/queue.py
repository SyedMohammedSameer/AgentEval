import heapq


class PriorityQueue:
    """Lowest priority value pops first; ties pop in insertion order."""

    def __init__(self):
        self._heap = []

    def push(self, priority: int, item) -> None:
        # BUG: with only (priority, item) on the heap, any tie in priority falls
        # through to comparing `item` - which reorders equal-priority entries by
        # payload and blows up entirely on payloads that define no ordering.
        heapq.heappush(self._heap, (priority, item))

    def pop(self):
        if not self._heap:
            raise IndexError("pop from an empty queue")
        _priority, item = heapq.heappop(self._heap)
        return item

    def __len__(self) -> int:
        return len(self._heap)
