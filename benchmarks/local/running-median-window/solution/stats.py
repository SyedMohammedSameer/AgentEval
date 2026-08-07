def moving_average(nums, k):
    out = []
    # There are len(nums) - k + 1 windows of width k, not len(nums) - k.
    for i in range(len(nums) - k + 1):
        window = nums[i:i + k]
        out.append(sum(window) / k)
    return out
