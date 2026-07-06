import re


def slugify(text: str) -> str:
    text = text.lower()
    # BUG: replaces each non-alphanumeric char with its own hyphen, and does not
    # strip leading/trailing hyphens.
    return re.sub(r"[^a-z0-9]", "-", text)
