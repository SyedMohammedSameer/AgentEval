from dataclasses import dataclass


@dataclass(frozen=True, order=True)
class Range:
    """A half-open interval [start, end)."""

    start: int
    end: int

    def is_empty(self) -> bool:
        return self.start >= self.end

    def overlaps(self, other: "Range") -> bool:
        # BUG: half-open ranges that touch at a boundary (end == other.start)
        # are contiguous and must be merged, but strict inequality rejects them.
        return self.start < other.end and other.start < self.end
