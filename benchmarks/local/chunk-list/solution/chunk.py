def chunk(lst, n):
    out = []
    # Step by n for consecutive chunks; stepping by 1 gives sliding windows.
    for i in range(0, len(lst), n):
        out.append(lst[i:i + n])
    return out
