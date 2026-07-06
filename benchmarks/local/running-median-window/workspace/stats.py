def moving_average(nums, k):
    out = []
    # BUG: range end should be len(nums) - k + 1, so the last window is dropped.
    for i in range(len(nums) - k):
        window = nums[i:i + k]
        out.append(sum(window) / k)
    return out
