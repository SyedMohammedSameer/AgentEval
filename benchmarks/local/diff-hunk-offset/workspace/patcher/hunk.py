from dataclasses import dataclass


class PatchError(Exception):
    """A hunk could not be applied."""


@dataclass(frozen=True)
class Hunk:
    """Replace `count` lines starting at 1-based `start` with `lines`."""

    start: int
    count: int
    lines: tuple
