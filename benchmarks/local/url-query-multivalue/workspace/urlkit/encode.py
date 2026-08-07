_UNRESERVED = set(
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "0123456789-_.~"
)


def quote(text: str) -> str:
    """Percent-encode `text` for use in a query string."""
    out = []
    for ch in text:
        if ch in _UNRESERVED:
            out.append(ch)
        elif ch == " ":
            out.append("+")
        else:
            # BUG: everything else is passed through unescaped, so a value
            # containing & or = silently corrupts the surrounding query string.
            out.append(ch)
    return "".join(out)


def build_query(params: dict) -> str:
    """Build a query string. A list value produces one pair per element."""
    parts = []
    for key, value in params.items():
        # BUG: a list is stringified as a whole rather than repeated, turning
        # {"tag": ["a", "b"]} into a single pair containing "['a', 'b']".
        parts.append(f"{quote(str(key))}={quote(str(value))}")
    return "&".join(parts)
