from router.routes import Route, is_dynamic, param_name


class Router:
    def __init__(self):
        self._routes: list[Route] = []

    def add(self, pattern: str, handler: str) -> None:
        self._routes.append(Route(pattern, handler))

    def match(self, path: str):
        """Return (handler, params) for `path`, or (None, {}) if nothing matches."""
        parts = [s for s in path.strip("/").split("/") if s]
        # BUG: the first route that matches wins, so precedence is registration
        # order rather than specificity - a dynamic route registered first
        # shadows a more specific static route.
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
                return route.handler, params
        return None, {}
