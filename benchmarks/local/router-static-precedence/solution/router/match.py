from router.routes import Route, is_dynamic, param_name


class Router:
    def __init__(self):
        self._routes: list[Route] = []

    def add(self, pattern: str, handler: str) -> None:
        self._routes.append(Route(pattern, handler))

    def match(self, path: str):
        """Return (handler, params) for `path`, or (None, {}) if nothing matches."""
        parts = [s for s in path.strip("/").split("/") if s]

        candidates = []
        for route in self._routes:
            segs = route.segments
            if len(segs) != len(parts):
                continue
            params = {}
            for seg, part in zip(segs, parts):
                if is_dynamic(seg):
                    params[param_name(seg)] = part
                elif seg != part:
                    break
            else:
                # Specificity: static segments outrank dynamic ones, compared
                # left to right, so the earliest static win decides.
                specificity = tuple(0 if is_dynamic(s) else 1 for s in segs)
                candidates.append((specificity, route.handler, params))

        if not candidates:
            return None, {}
        best = max(candidates, key=lambda c: c[0])
        return best[1], best[2]
