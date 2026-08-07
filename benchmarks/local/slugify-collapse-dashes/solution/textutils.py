import re


def slugify(text: str) -> str:
    text = text.lower()
    # Collapse each *run* of non-alphanumeric characters to one hyphen, then trim
    # the hyphens a leading or trailing run leaves behind.
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")
