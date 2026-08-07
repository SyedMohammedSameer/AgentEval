from dataclasses import dataclass
from typing import Callable


class UnknownTransition(Exception):
    """No transition matches this event from the current state."""


@dataclass(frozen=True)
class Transition:
    source: str
    event: str
    target: str
    guard: Callable | None = None   # ctx -> bool; the move only happens if True
