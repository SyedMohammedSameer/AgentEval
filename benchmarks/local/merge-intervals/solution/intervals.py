def merge(intervals):
    intervals = sorted(intervals)
    merged = []
    for start, end in intervals:
        # <= so intervals that merely touch, like [1,2] and [2,3], combine.
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return merged
