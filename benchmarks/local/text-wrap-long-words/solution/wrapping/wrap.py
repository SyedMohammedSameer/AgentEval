def wrap_text(text: str, width: int) -> list[str]:
    """Wrap `text` into lines no longer than `width` characters."""
    if width <= 0:
        raise ValueError("width must be positive")

    lines: list[str] = []
    current: list[str] = []
    current_len = 0

    def flush():
        nonlocal current, current_len
        if current:
            lines.append(" ".join(current))
            current = []
            current_len = 0

    for word in text.split():
        # Hard-split any word that cannot fit on a line of its own.
        while len(word) > width:
            flush()
            lines.append(word[:width])
            word = word[width:]

        # +1 for the space that would join this word to the current line.
        needed = len(word) if not current else current_len + 1 + len(word)
        if needed > width:
            flush()
            needed = len(word)
        current.append(word)
        current_len = needed

    flush()
    return lines
