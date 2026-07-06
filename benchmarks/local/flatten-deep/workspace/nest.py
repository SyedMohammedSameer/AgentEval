def flatten(nested):
    out = []
    for item in nested:
        if isinstance(item, list):
            # BUG: only one level — nested sublists stay nested.
            out.extend(item)
        else:
            out.append(item)
    return out
