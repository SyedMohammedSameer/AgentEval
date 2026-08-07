def encode(s: str) -> str:
    if not s:
        return ""
    out = []
    prev, count = s[0], 1
    for ch in s[1:]:
        if ch == prev:
            count += 1
        else:
            out.append(f"{prev}{count}")
            prev, count = ch, 1
    # The loop only emits a run when it *changes*, so the final run needs
    # flushing after it ends.
    out.append(f"{prev}{count}")
    return "".join(out)
