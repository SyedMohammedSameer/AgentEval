class EventBus:
    def __init__(self):
        # list of (priority, handler)
        self._handlers: list[tuple[int, object]] = []

    def subscribe(self, handler, priority: int = 0) -> None:
        # BUG: inserting at the front means that among handlers of equal
        # priority the most recently registered runs first, reversing
        # registration order. The stable sort below preserves that inversion.
        self._handlers.insert(0, (priority, handler))
        self._handlers.sort(key=lambda pair: -pair[0])

    def unsubscribe(self, handler) -> None:
        # BUG: removing in place mutates the very list publish() is iterating.
        for i, (_p, h) in enumerate(self._handlers):
            if h is handler:
                del self._handlers[i]
                break

    def publish(self, event) -> list:
        results = []
        # BUG: iterating the live list while a handler removes itself shifts the
        # remaining items down and skips the next one.
        for _priority, handler in self._handlers:
            results.append(handler(event))
        return results
