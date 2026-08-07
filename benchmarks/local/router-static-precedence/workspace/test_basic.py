from router.match import Router


def test_static_route():
    r = Router()
    r.add("/users/me", "me")
    assert r.match("/users/me") == ("me", {})


def test_static_beats_dynamic_registered_first():
    r = Router()
    r.add("/users/{id}", "by_id")
    r.add("/users/me", "me")
    assert r.match("/users/me") == ("me", {})
