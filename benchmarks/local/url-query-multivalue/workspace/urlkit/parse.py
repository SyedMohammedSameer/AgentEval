def unquote(text: str) -> str:
    """Reverse `quote`: decode %XX escapes and turn + back into a space."""
    text = text.replace("+", " ")
    out = bytearray()
    i = 0
    while i < len(text):
        if text[i] == "%" and i + 3 <= len(text):
            try:
                out.append(int(text[i + 1:i + 3], 16))
                i += 3
                continue
            except ValueError:
                pass
        out.extend(text[i].encode("utf-8"))
        i += 1
    return out.decode("utf-8", errors="replace")


def parse_query(query: str) -> dict:
    """Parse a query string into {key: [values]}."""
    out: dict = {}
    if not query:
        return out
    for part in query.split("&"):
        if not part:
            continue
        key, _, value = part.partition("=")
        out.setdefault(unquote(key), []).append(unquote(value))
    return out
