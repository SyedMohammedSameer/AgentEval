def merge(intervals):
    intervals = sorted(intervals)
    merged = []
    for start, end in intervals:
        # BUG: strict `<` fails to merge touching intervals like [1,2],[2,3].
        if merged and start < merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return merged
