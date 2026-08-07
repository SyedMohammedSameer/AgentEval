import re

_ROTATED = re.compile(r"^(?P<base>.+)\.(?P<index>\d+)$")


def rotated_name(base: str, index: int) -> str:
    return f"{base}.{index}"


def parse_index(filename: str):
    """Return the rotation index of `filename`, or None if it is not rotated."""
    m = _ROTATED.match(filename)
    return int(m.group("index")) if m else None


def sort_rotations(filenames: list) -> list:
    """Sort rotated files by age: index 1 is the most recent rotation."""
    def key(filename: str):
        index = parse_index(filename)
        # Unrotated names have no index; keep them first and stable by name.
        return (index is not None, index if index is not None else 0, filename)

    return sorted(filenames, key=key)
