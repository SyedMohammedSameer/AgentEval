def parse_line(line: str) -> list[str]:
    """Split one CSV line into fields, honoring double-quoted fields."""
    fields: list[str] = []
    current: list[str] = []
    in_quotes = False
    i = 0
    while i < len(line):
        ch = line[i]
        if in_quotes:
            if ch == '"':
                # A doubled quote inside a quoted field is one literal quote.
                if i + 1 < len(line) and line[i + 1] == '"':
                    current.append('"')
                    i += 2
                    continue
                in_quotes = False
            else:
                current.append(ch)
        else:
            if ch == '"' and not current:
                # Quotes only open a field at its start; elsewhere they are literal.
                in_quotes = True
            elif ch == ",":
                fields.append("".join(current))
                current = []
            else:
                current.append(ch)
        i += 1
    fields.append("".join(current))
    return fields


def parse(text: str) -> list[list[str]]:
    """Parse a whole CSV document into rows of fields."""
    return [parse_line(line) for line in text.splitlines() if line]
