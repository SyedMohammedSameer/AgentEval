from logrotate.naming import parse_index, sort_rotations


def files_to_delete(filenames: list, keep: int) -> list:
    """Return the rotated files that exceed the retention limit."""
    if keep < 0:
        raise ValueError("keep must be non-negative")
    rotated = [f for f in filenames if parse_index(f) is not None]
    ordered = sort_rotations(rotated)
    return ordered[keep:]
