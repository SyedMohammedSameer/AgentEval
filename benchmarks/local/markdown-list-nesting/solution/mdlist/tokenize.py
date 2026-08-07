from dataclasses import dataclass

TAB_WIDTH = 4


@dataclass(frozen=True)
class Item:
    indent: int   # indentation in columns
    text: str


def tokenize(source: str) -> list:
    """Extract list items, ignoring blank and non-list lines."""
    items = []
    for raw in source.splitlines():
        if not raw.strip():
            continue
        stripped = raw.lstrip(" \t")
        if not stripped.startswith("- "):
            continue
        prefix = raw[: len(raw) - len(stripped)]
        indent = 0
        for ch in prefix:
            if ch == "\t":
                # A tab advances to the next tab stop, not by one column.
                indent += TAB_WIDTH - (indent % TAB_WIDTH)
            else:
                indent += 1
        items.append(Item(indent=indent, text=stripped[2:].strip()))
    return items
