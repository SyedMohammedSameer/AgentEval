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
            # BUG: an unmatched event is swallowed instead of raising
            # UnknownTransition, so a misspelled event looks like a no-op.
            return False
        # BUG: the move is applied before the guard is consulted, so a rejected
        # transition still changes state and is still recorded in history.
        self.state = t.target
        self.history.append(t.target)
        return t.guard is None or t.guard(ctx or {})
