import pytest

from api.paginate import page, walk


def test_last_page_has_no_cursor():
    p = page([1, 2, 3, 4], cursor=2, limit=2)
    assert p.items == [3, 4]
    assert p.next_cursor is None


def test_exact_multiple_terminates():
    assert list(walk([1, 2, 3, 4], limit=2)) == [1, 2, 3, 4]


def test_ragged_final_page():
    p = page([1, 2, 3], cursor=2, limit=2)
    assert p.items == [3]
    assert p.next_cursor is None


def test_empty_collection():
    p = page([], cursor=0, limit=3)
    assert p.items == []
    assert p.next_cursor is None
    assert list(walk([], limit=3)) == []


def test_limit_larger_than_collection():
    p = page([1, 2], cursor=0, limit=10)
    assert p.items == [1, 2]
    assert p.next_cursor is None


def test_limit_of_one():
    assert list(walk([1, 2, 3], limit=1)) == [1, 2, 3]


def test_invalid_limit_rejected():
    with pytest.raises(ValueError):
        page([1, 2], cursor=0, limit=0)
