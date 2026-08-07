from router.match import Router


def test_dynamic_still_matches_other_values():
    r = Router()
    r.add("/users/{id}", "by_id")
    r.add("/users/me", "me")
    assert r.match("/users/42") == ("by_id", {"id": "42"})


def test_specificity_at_later_segment():
    r = Router()
    r.add("/a/{x}/c", "dynamic")
    r.add("/a/b/c", "static")
    assert r.match("/a/b/c") == ("static", {})
    assert r.match("/a/z/c") == ("dynamic", {"x": "z"})


def test_leftmost_static_segment_wins():
    r = Router()
    r.add("/{a}/static", "left_dynamic")
    r.add("/static/{b}", "left_static")
    assert r.match("/static/static") == ("left_static", {"b": "static"})


def test_segment_count_must_match():
    r = Router()
    r.add("/users/{id}", "by_id")
    assert r.match("/users") == (None, {})
    assert r.match("/users/1/posts") == (None, {})


def test_multiple_params():
    r = Router()
    r.add("/u/{uid}/p/{pid}", "post")
    assert r.match("/u/7/p/9") == ("post", {"uid": "7", "pid": "9"})


def test_no_match_returns_none():
    r = Router()
    r.add("/a", "a")
    assert r.match("/b") == (None, {})


def test_trailing_slashes_ignored():
    r = Router()
    r.add("/users/me", "me")
    assert r.match("/users/me/") == ("me", {})
