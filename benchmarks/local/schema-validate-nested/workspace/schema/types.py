from dataclasses import dataclass, field


@dataclass
class Field:
    kind: str                       # "str" | "int" | "object"
    required: bool = True
    fields: dict = field(default_factory=dict)   # for kind == "object"


PYTHON_TYPES = {"str": str, "int": int, "object": dict}
