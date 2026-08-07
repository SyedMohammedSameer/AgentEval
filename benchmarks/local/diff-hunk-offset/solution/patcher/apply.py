from patcher.hunk import Hunk, PatchError


def apply_hunks(text: str, hunks: list) -> str:
    """Apply `hunks` to `text`, returning the patched text."""
    lines = text.split("\n")
    # Running drift between original line numbers and current ones.
    offset = 0
    for hunk in sorted(hunks, key=lambda h: h.start):
        idx = hunk.start - 1 + offset
        if idx < 0 or idx + hunk.count > len(lines):
            raise PatchError(f"hunk at line {hunk.start} does not fit")
        lines[idx:idx + hunk.count] = list(hunk.lines)
        offset += len(hunk.lines) - hunk.count
    return "\n".join(lines)
