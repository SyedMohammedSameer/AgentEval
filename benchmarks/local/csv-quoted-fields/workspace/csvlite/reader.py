def parse_line(line: str) -> list[str]:
    """Split one CSV line into fields, honoring double-quoted fields."""
    # BUG: a naive split ignores quoting entirely, so quoted fields containing
    # commas are torn apart and the quote characters are left in the values.
    return line.split(",")


def parse(text: str) -> list[list[str]]:
    """Parse a whole CSV document into rows of fields."""
    return [parse_line(line) for line in text.splitlines() if line]
