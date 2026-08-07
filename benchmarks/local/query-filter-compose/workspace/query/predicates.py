def eq(field, value):
    """Row's `field` equals `value`."""
    return lambda row: row.get(field) == value


def gt(field, value):
    """Row's `field` is present and greater than `value`."""
    return lambda row: row.get(field) is not None and row[field] > value


def contains(field, needle):
    """Row's `field` contains `needle` (missing fields never match)."""
    return lambda row: needle in (row.get(field) or "")
