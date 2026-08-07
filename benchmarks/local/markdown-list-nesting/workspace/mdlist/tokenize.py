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
        # BUG: every prefix character counts as one column, so a tab measures 1
        # instead of advancing to the next TAB_WIDTH tab stop. Tab-indented
        # children then appear shallower than their space-indented parents.
        indent = len(prefix)
        items.append(Item(indent=indent, text=stripped[2:].strip()))
    return items
