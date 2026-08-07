from patcher.hunk import Hunk, PatchError


def apply_hunks(text: str, hunks: list) -> str:
    """Apply `hunks` to `text`, returning the patched text."""
    lines = text.split("\n")
    for hunk in sorted(hunks, key=lambda h: h.start):
        idx = hunk.start - 1
        if idx < 0 or idx + hunk.count > len(lines):
            raise PatchError(f"hunk at line {hunk.start} does not fit")
        # BUG: hunk positions refer to the original text, but each applied hunk
        # shifts everything after it by (len(lines) - count). That drift is
        # never accounted for, so every hunk after the first is misplaced as
        # soon as one of them changes the line count.
        lines[idx:idx + hunk.count] = list(hunk.lines)
    return "\n".join(lines)
