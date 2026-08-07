from deps.graph import CycleError, Graph


def resolve_order(edges: dict[str, list[str]]) -> list[str]:
    """Return an install order: every dependency precedes its dependent."""
    graph = Graph(edges)
    order: list[str] = []
    done: set[str] = set()      # fully emitted
    on_stack: set[str] = set()  # currently being visited -> a revisit means a cycle

    def visit(node: str):
        if node in done:
            return
        if node in on_stack:
            raise CycleError(node)
        on_stack.add(node)
        for dep in graph.deps_of(node):
            visit(dep)
        on_stack.discard(node)
        done.add(node)
        order.append(node)

    for node in graph.nodes():
        visit(node)
    return order
