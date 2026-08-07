def search(arr, target):
    # hi is an inclusive bound, so it starts one past the last valid index only
    # if the loop condition were `<`. With `<=` it must be len(arr) - 1.
    lo, hi = 0, len(arr) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            lo = mid + 1
        else:
            hi = mid - 1
    return -1
