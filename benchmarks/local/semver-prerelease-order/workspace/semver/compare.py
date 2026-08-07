from semver.parse import Version, parse


def _key(v: Version):
    # BUG: prerelease identifiers are compared as raw strings, so "10" < "2",
    # and an empty prerelease tuple sorts *before* a populated one, making
    # 1.0.0 older than 1.0.0-alpha. Semver requires the opposite.
    return (v.major, v.minor, v.patch, v.prerelease)


def compare(a: str, b: str) -> int:
    """Return -1 if a < b, 0 if equal, 1 if a > b."""
    ka, kb = _key(parse(a)), _key(parse(b))
    if ka < kb:
        return -1
    return 0 if ka == kb else 1
