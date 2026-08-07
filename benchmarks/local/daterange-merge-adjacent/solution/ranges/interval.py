from dataclasses import dataclass


@dataclass(frozen=True, order=True)
class Range:
    """A half-open interval [start, end)."""

    start: int
    end: int

    def is_empty(self) -> bool:
        return self.start >= self.end

    def overlaps(self, other: "Range") -> bool:
        # Half-open ranges that touch at a boundary are contiguous, so <= is
        # the correct comparison for mergeability.
        return self.start <= other.end and other.start <= self.end
