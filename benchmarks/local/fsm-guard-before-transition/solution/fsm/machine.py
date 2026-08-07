from fsm.transitions import Transition, UnknownTransition


class Machine:
    def __init__(self, initial: str, transitions):
        self.state = initial
        self.transitions = list(transitions)
        self.history = [initial]

    def _find(self, event: str):
        for t in self.transitions:
            if t.source == self.state and t.event == event:
                return t
        return None

    def fire(self, event: str, ctx: dict | None = None) -> bool:
        """Apply `event`; returns True if the machine moved."""
        t = self._find(event)
        if t is None:
            raise UnknownTransition(f"no transition for {event!r} from {self.state!r}")
        # Consult the guard first: a rejected transition must leave both the
        # state and the history exactly as they were.
        if t.guard is not None and not t.guard(ctx or {}):
            return False
        self.state = t.target
        self.history.append(t.target)
        return True
