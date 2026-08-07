from deps.graph import CycleError, Graph


def resolve_order(edges: dict[str, list[str]]) -> list[str]:
    """Return an install order: every dependency precedes its dependent."""
    graph = Graph(edges)
    order: list[str] = []

    def visit(node: str):
        # BUG: nothing records which nodes have already been emitted, so a node
        # reachable by two paths is appended twice. BUG: nothing tracks the nodes
        # currently on the recursion stack, so a cycle recurses until Python
        # raises RecursionError instead of CycleError.
        for dep in graph.deps_of(node):
            visit(dep)
        order.append(node)

    for node in graph.nodes():
        visit(node)
    return order
