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
            # BUG: the merged end takes the incoming range's end unconditionally,
            # so a range fully contained in `last` shrinks it.
            out[-1] = Range(last.start, current.end)
        else:
            out.append(current)
    return out
