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
            self._data.popitem(last=False)

    def get(self, key, default=None):
        entry = self._data.get(key, MISSING)
        if entry is MISSING:
            return default
        value, stored_at = entry
        if self.clock.time() - stored_at > self.ttl:
            del self._data[key]
            return default
        self._data.move_to_end(key)
        return value

    def __len__(self) -> int:
        return len(self._data)
