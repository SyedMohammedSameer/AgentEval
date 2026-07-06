def chunk(lst, n):
    out = []
    # BUG: step of 1 yields overlapping windows instead of consecutive chunks.
    for i in range(0, len(lst)):
        out.append(lst[i:i + n])
    return out
