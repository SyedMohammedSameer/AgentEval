from dataclasses import dataclass


@dataclass(frozen=True)
class Route:
    pattern: str
    handler: str

    @property
    def segments(self) -> list[str]:
        return [s for s in self.pattern.strip("/").split("/") if s]


def is_dynamic(segment: str) -> bool:
    return segment.startswith("{") and segment.endswith("}")


def param_name(segment: str) -> str:
    return segment[1:-1]
