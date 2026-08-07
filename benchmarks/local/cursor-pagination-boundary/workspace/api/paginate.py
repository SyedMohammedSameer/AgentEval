from api.models import Page


def page(records, cursor: int = 0, limit: int = 2) -> Page:
    """Return `limit` records starting at `cursor`, plus the cursor to continue from."""
    if limit <= 0:
        raise ValueError("limit must be positive")
    window = records[cursor:cursor + limit]
    # BUG: the next cursor points at the last item returned rather than past it,
    # so the following page repeats that record. BUG: a next cursor is emitted
    # even when the window reached the end of the collection.
    next_cursor = cursor + limit - 1
    return Page(items=window, next_cursor=next_cursor)


def walk(records, limit: int = 2):
    """Yield every record by following cursors to exhaustion."""
    cursor: int | None = 0
    while cursor is not None:
        p = page(records, cursor, limit)
        yield from p.items
        if p.next_cursor is not None:
            # Two ways a broken cursor loops forever: it stops advancing, or it
            # runs off the end and keeps handing back empty pages. Neither should
            # hang a caller, so both fail loudly.
            if p.next_cursor <= cursor:
                raise RuntimeError(f"cursor did not advance past {cursor}")
            if not p.items:
                raise RuntimeError(f"empty page at cursor {cursor} with more promised")
        cursor = p.next_cursor
