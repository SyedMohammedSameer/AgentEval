def wrap_text(text: str, width: int) -> list[str]:
    """Wrap `text` into lines no longer than `width` characters."""
    if width <= 0:
        raise ValueError("width must be positive")

    lines: list[str] = []
    current = ""
    for word in text.split():
        # BUG: a word longer than `width` is appended whole, producing an
        # over-long line instead of being hard-split. BUG: words are joined by
        # appending a trailing space, which is never stripped.
        if len(current) + len(word) <= width:
            current += word + " "
        else:
            lines.append(current)
            current = word + " "
    if current:
        lines.append(current)
    return lines
