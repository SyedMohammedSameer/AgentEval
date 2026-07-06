def search(arr, target):
    lo, hi = 0, len(arr)  # BUG: hi should be len(arr) - 1 for inclusive bounds.
    while lo <= hi:
        mid = (lo + hi) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            lo = mid + 1
        else:
            hi = mid - 1
    return -1
