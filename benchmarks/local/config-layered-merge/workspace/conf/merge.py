def deep_merge(base: dict, override: dict) -> dict:
    """Merge `override` into `base`, returning a new dict."""
    out = dict(base)
    # BUG: dict.update replaces nested sections wholesale instead of merging
    # them, so {"db": {"port": 2}} wipes out db.host.
    out.update(override)
    return out
