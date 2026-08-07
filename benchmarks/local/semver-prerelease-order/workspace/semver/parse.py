import re
from dataclasses import dataclass

_PATTERN = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?$")


@dataclass(frozen=True)
class Version:
    major: int
    minor: int
    patch: int
    prerelease: tuple = ()


def parse(text: str) -> Version:
    m = _PATTERN.match(text.strip())
    if not m:
        raise ValueError(f"not a version: {text!r}")
    major, minor, patch, pre = m.groups()
    parts = tuple(pre.split(".")) if pre else ()
    return Version(int(major), int(minor), int(patch), parts)
