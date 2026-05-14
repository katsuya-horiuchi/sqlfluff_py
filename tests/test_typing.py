from sqlfluff_py.typing import Position


def test_position_equality() -> None:
    assert Position(1, 18) == Position(1, 18)



def test_position_auto_from_tuple() -> None:
    assert Position.auto((3, 7)) == Position(3, 7)


def test_position_auto_from_dict() -> None:
    assert Position.auto({"x": 3, "y": 7}) == Position(3, 7)


def test_position_auto_from_position() -> None:
    p = Position(3, 7)
    assert Position.auto(p) is p
