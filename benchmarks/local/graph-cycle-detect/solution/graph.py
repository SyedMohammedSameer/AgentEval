def has_cycle(adj):
    # Three-color DFS: grey marks nodes on the current recursion stack, so only a
    # back-edge counts as a cycle. A plain visited set also flags cross-edges,
    # which are legal in a DAG.
    WHITE, GREY, BLACK = 0, 1, 2
    color = {}

    def dfs(node):
        color[node] = GREY
        for nxt in adj.get(node, []):
            state = color.get(nxt, WHITE)
            if state == GREY:
                return True
            if state == WHITE and dfs(nxt):
                return True
        color[node] = BLACK
        return False

    return any(color.get(n, WHITE) == WHITE and dfs(n) for n in list(adj))
