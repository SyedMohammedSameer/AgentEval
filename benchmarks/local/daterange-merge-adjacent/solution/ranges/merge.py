from ranges.interval import Range


def merge_all(ranges: list[Range]) -> list[Range]:
    """Collapse overlapping or adjacent ranges into a minimal sorted list."""
    items = sorted(r for r in ranges if not r.is_empty())
    if not items:
        return []

    out = [items[0]]
    for current in items[1:]:
        last = out[-1]
        if last.overlaps(current):
            # Take the furthest end so a contained range never shrinks its parent.
            out[-1] = Range(last.start, max(last.end, current.end))
        else:
            out.append(current)
    return out
