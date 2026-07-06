def has_cycle(adj):
    visited = set()

    def dfs(node):
        # BUG: a plain visited set flags any re-encountered node as a cycle,
        # which is wrong for DAGs with shared descendants.
        if node in visited:
            return True
        visited.add(node)
        for nxt in adj.get(node, []):
            if dfs(nxt):
                return True
        return False

    return any(dfs(n) for n in list(adj))
