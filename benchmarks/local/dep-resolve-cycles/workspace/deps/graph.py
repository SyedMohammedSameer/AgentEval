class CycleError(Exception):
    """Raised when the dependency graph cannot be linearized."""

    def __init__(self, node):
        super().__init__(f"dependency cycle involving {node!r}")
        self.node = node


class Graph:
    def __init__(self, edges: dict[str, list[str]]):
        # node -> list of nodes it depends on
        self.edges = {k: list(v) for k, v in edges.items()}

    def deps_of(self, node: str) -> list[str]:
        return self.edges.get(node, [])

    def nodes(self) -> list[str]:
        seen = list(self.edges)
        for targets in self.edges.values():
            for t in targets:
                if t not in seen:
                    seen.append(t)
        return seen
