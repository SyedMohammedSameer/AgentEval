from itertools import count


class EventBus:
    def __init__(self):
        # list of (priority, sequence, handler); sequence preserves registration
        # order among equal priorities.
        self._handlers: list[tuple[int, int, object]] = []
        self._seq = count()

    def subscribe(self, handler, priority: int = 0) -> None:
        self._handlers.append((priority, next(self._seq), handler))
        self._handlers.sort(key=lambda triple: (-triple[0], triple[1]))

    def unsubscribe(self, handler) -> None:
        self._handlers = [t for t in self._handlers if t[2] is not handler]

    def publish(self, event) -> list:
        results = []
        # Iterate a snapshot so handlers may subscribe/unsubscribe during dispatch.
        for _priority, _seq, handler in list(self._handlers):
            results.append(handler(event))
        return results
