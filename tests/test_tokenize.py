from sqlfluff_py.tokenize import Position


def test_position() -> None:
    assert Position(1, 18) == Position(1, 18)
    assert Position(1, 18) < Position(2, 0)
