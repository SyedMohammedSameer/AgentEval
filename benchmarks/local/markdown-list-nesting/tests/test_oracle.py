from mdlist.tokenize import tokenize
from mdlist.tree import build_tree


def test_tab_advances_to_the_next_tab_stop():
    items = tokenize("- a\n\t- b")
    assert [i.indent for i in items] == [0, 4]


def test_tab_and_space_indentation_agree():
    tabbed = build_tree("- a\n\t- b")
    spaced = build_tree("- a\n    - b")
    assert tabbed == spaced


def test_deep_dedent_keeps_the_full_subtree():
    tree = build_tree("- a\n  - b\n    - c\n- d")
    assert len(tree) == 2
    assert tree[1] == {"text": "d", "children": []}
    assert tree[0]["children"][0]["children"][0]["text"] == "c"


def test_siblings_at_the_same_indent():
    assert [n["text"] for n in build_tree("- a\n- b\n- c")] == ["a", "b", "c"]


def test_dedent_to_an_intermediate_level():
    tree = build_tree("- a\n  - b\n    - c\n  - d")
    assert [c["text"] for c in tree[0]["children"]] == ["b", "d"]


def test_blank_and_non_list_lines_are_ignored():
    tree = build_tree("intro\n\n- a\nprose\n  - b\n")
    assert [n["text"] for n in tree] == ["a"]
    assert tree[0]["children"][0]["text"] == "b"


def test_empty_source():
    assert build_tree("") == []
