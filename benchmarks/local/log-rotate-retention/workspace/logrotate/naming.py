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
    # BUG: a lexical sort orders "app.log.10" before "app.log.2", so once the
    # index reaches two digits the notion of "oldest" is wrong.
    return sorted(filenames)
