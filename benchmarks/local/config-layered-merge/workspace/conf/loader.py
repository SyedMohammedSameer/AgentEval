from conf.merge import deep_merge


def load_layers(layers):
    """Apply config layers left to right; later layers win."""
    result: dict = {}
    for layer in layers:
        result = deep_merge(result, layer)
    return result
