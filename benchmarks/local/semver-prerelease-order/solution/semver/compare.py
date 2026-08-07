from semver.parse import Version, parse


def _identifier_key(part: str):
    # Numeric identifiers compare numerically and always rank below
    # alphanumeric ones; the leading flag encodes that ordering.
    if part.isdigit():
        return (0, int(part), "")
    return (1, 0, part)


def _key(v: Version):
    # A release has no prerelease and outranks any prerelease of the same
    # version, so the presence flag is 1 for releases and 0 otherwise.
    has_release = 0 if v.prerelease else 1
    return (
        v.major,
        v.minor,
        v.patch,
        has_release,
        tuple(_identifier_key(p) for p in v.prerelease),
    )


def compare(a: str, b: str) -> int:
    """Return -1 if a < b, 0 if equal, 1 if a > b."""
    ka, kb = _key(parse(a)), _key(parse(b))
    if ka < kb:
        return -1
    return 0 if ka == kb else 1
