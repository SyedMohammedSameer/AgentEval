from collections import OrderedDict

from cache.clock import ManualClock

MISSING = object()


class TTLCache:
    def __init__(self, capacity: int, ttl: float, clock=None):
        self.capacity = capacity
        self.ttl = ttl
        self.clock = clock or ManualClock()
        self._data: OrderedDict = OrderedDict()

    def set(self, key, value) -> None:
        self._data[key] = (value, self.clock.time())
        self._data.move_to_end(key)
        if len(self._data) > self.capacity:
            # Evict the oldest entry.
            self._data.popitem(last=False)

    def get(self, key, default=None):
        entry = self._data.get(key, MISSING)
        if entry is MISSING:
            return default
        value, _stored_at = entry
        # BUG: the stored timestamp is never compared against the TTL, so expired
        # entries are served indefinitely. BUG: a hit does not refresh recency,
        # so the LRU order reflects insertion order only.
        return value

    def __len__(self) -> int:
        return len(self._data)
