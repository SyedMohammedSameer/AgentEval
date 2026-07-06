def dedup(items):
    # BUG: set() destroys ordering.
    return list(set(items))
