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
    # BUG: the final run (prev/count) is never appended.
    return "".join(out)
