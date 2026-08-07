from mdlist.tree import build_tree


def test_simple_nesting():
    tree = build_tree("- a\n  - b")
    assert tree == [{"text": "a", "children": [{"text": "b", "children": []}]}]


def test_dedent_by_two_levels_returns_to_root():
    tree = build_tree("- a\n  - b\n    - c\n- d")
    assert [n["text"] for n in tree] == ["a", "d"]
