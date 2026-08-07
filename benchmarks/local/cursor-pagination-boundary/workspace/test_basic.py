from api.paginate import page, walk


def test_first_page():
    p = page([1, 2, 3, 4, 5], cursor=0, limit=2)
    assert p.items == [1, 2]
    assert p.next_cursor == 2


def test_walk_yields_each_once():
    assert list(walk([1, 2, 3, 4, 5], limit=2)) == [1, 2, 3, 4, 5]
