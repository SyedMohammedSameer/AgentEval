from graph import has_cycle


def test_dag_shared_descendant():
    # a->b, a->c, b->d, c->d : NOT a cycle despite d seen twice.
    assert has_cycle({"a": ["b", "c"], "b": ["d"], "c": ["d"], "d": []}) is False


def test_self_loop():
    assert has_cycle({"a": ["a"]}) is True


def test_long_cycle():
    assert has_cycle({"a": ["b"], "b": ["c"], "c": ["a"]}) is True


def test_tree():
    assert has_cycle({"r": ["x", "y"], "x": [], "y": ["z"], "z": []}) is False
