from schema.types import PYTHON_TYPES, Field


def validate(value: dict, schema: dict[str, Field], path: str = "") -> list[str]:
    """Return a list of human-readable error strings; empty means valid."""
    errors: list[str] = []
    for name, spec in schema.items():
        where = f"{path}.{name}" if path else name

        if name not in value:
            # BUG: absence is reported regardless of whether the field is required.
            errors.append(f"{where}: missing required field")
            continue

        actual = value[name]
        expected = PYTHON_TYPES[spec.kind]
        if not isinstance(actual, expected):
            errors.append(f"{where}: expected {spec.kind}, got {type(actual).__name__}")
            continue

        # BUG: nested object schemas are never validated, so errors inside a
        # nested dict are silently ignored.
    return errors
