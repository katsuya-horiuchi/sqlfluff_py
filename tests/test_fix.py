import pathlib
import re
from dataclasses import dataclass

import pandas as pd
import pytest

from sqlfluff_py.fix import fix_script, _adjust_end, _adjust_start, _quote
from sqlfluff_py.typing import Position

TESTS_DIR = pathlib.Path(__file__).parent


@dataclass
class Case:
    dialect: str
    name: str

    def __str__(self) -> str:
        # pytest uses this via ids=str in parametrize to generate test IDs
        return f"{self.dialect}-{self.name}"


def _collect_cases() -> list[Case]:
    cases = []
    for dialect in sorted(TESTS_DIR.iterdir()):
        if not dialect.is_dir():
            continue
        for case in sorted(dialect.iterdir()):
            if (case / "input.py").exists():
                cases.append(Case(dialect.name, case.name))
    return cases


@pytest.mark.parametrize("case", _collect_cases(), ids=str)
def test_fix(case: Case) -> None:
    directory = TESTS_DIR / case.dialect / case.name
    result = fix_script(
        (directory / "input.py").read_text(), re.compile("sql"), case.dialect
    )
    assert result == (directory / "expected.py").read_text()


@dataclass
class QuoteCase:
    id: str
    indent: int
    query: str
    expected: str

    def __str__(self) -> str:
        return self.id


quote_cases = [
    QuoteCase(
        id="single_line",
        indent=0,
        query="SELECT 1",
        expected='"SELECT 1"',
    ),
    QuoteCase(
        id="single_line_fstring",
        indent=0,
        query="SELECT __placeholder_0__",
        expected='f"SELECT __placeholder_0__"',
    ),
    QuoteCase(
        id="multiline_indent0",
        indent=0,
        query="""    SELECT
    FROM t""",
        expected='''"""
    SELECT
    FROM t
"""''',
    ),
    QuoteCase(
        id="multiline_indent1",
        indent=1,
        query="""    SELECT
    FROM t""",
        expected='''"""
    SELECT
    FROM t
    """''',
    ),
    QuoteCase(
        id="multiline_fstring",
        query="""    SELECT __placeholder_0__
    FROM t""",
        indent=0,
        expected='''f"""
    SELECT __placeholder_0__
    FROM t
"""''',
    ),
]


@pytest.mark.parametrize("case", quote_cases, ids=str)
def test_quote(case: QuoteCase) -> None:
    assert _quote(case.query, case.indent) == case.expected


def _make_row(
    idx: int, start: Position, end: Position, string: str = "tok"
) -> pd.Series:
    row = pd.Series({"start": start, "end": end, "string": string})
    row.name = idx
    return row


def test_adjust_start_before_index() -> None:
    row = _make_row(2, Position(5, 0), Position(5, 3))
    assert _adjust_start(row, index=5, delta=-3) == Position(5, 0)


def test_adjust_start_at_index() -> None:
    # row.name == index → not adjusted
    row = _make_row(5, Position(5, 0), Position(5, 3))
    assert _adjust_start(row, index=5, delta=-3) == Position(5, 0)


def test_adjust_start_after_index() -> None:
    row = _make_row(6, Position(10, 0), Position(10, 3))
    assert _adjust_start(row, index=5, delta=-3) == Position(7, 0)


def test_adjust_start_positive_delta() -> None:
    row = _make_row(6, Position(10, 4), Position(10, 8))
    assert _adjust_start(row, index=5, delta=2) == Position(12, 4)


def test_adjust_end_before_index() -> None:
    row = _make_row(3, Position(5, 0), Position(5, 10))
    assert _adjust_end(row, index=5, delta=-3) == Position(5, 10)


def test_adjust_end_after_index() -> None:
    row = _make_row(6, Position(10, 0), Position(12, 5))
    # only the row is shifted, column is unchanged
    assert _adjust_end(row, index=5, delta=2) == Position(14, 5)
