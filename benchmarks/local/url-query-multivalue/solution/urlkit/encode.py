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
            # Percent-encode per UTF-8 byte, so non-ASCII survives the round trip.
            for byte in ch.encode("utf-8"):
                out.append(f"%{byte:02X}")
    return "".join(out)


def build_query(params: dict) -> str:
    """Build a query string. A list value produces one pair per element."""
    parts = []
    for key, value in params.items():
        values = value if isinstance(value, (list, tuple)) else [value]
        for item in values:
            parts.append(f"{quote(str(key))}={quote(str(item))}")
    return "&".join(parts)
