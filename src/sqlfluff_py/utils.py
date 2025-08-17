import logging
from typing import Tuple
import pandas as pd
from sqlfluff_py.typing import TYPE_INDEX


_logger = logging.getLogger(__name__)


def quote(query: str, indent: int) -> str:
    if "\n" in query:
        trailing_whitespace = f"{'    ' * indent}"
        f_prefix = "f" if "[placeholder_" in query else ""
        query = f'{f_prefix}"""\n{query}\n{trailing_whitespace}"""'
    else:
        query = f'"{query}"'
    return query


def _adjust_position(
    row: pd.Series, index: TYPE_INDEX, delta: int, attr: str
) -> Tuple[int, int]:
    assert isinstance(row.name, TYPE_INDEX)
    pos_original: Tuple[int, int] = row[attr]

    if row.name <= index:
        return row[attr]  # type: ignore
    pos = (pos_original[0] + delta, pos_original[1])
    if pos != pos_original:
        _logger.debug(
            f"Position has been adjusted for {attr} for "
            f"token `{row['string']}`. "
            f"Original: {pos_original}. New: {pos}"
        )
    return pos


def adjust_start(
    row: pd.Series, index: TYPE_INDEX, delta: int
) -> Tuple[int, int]:
    return _adjust_position(row, index, delta, "start")


def adjust_end(
    row: pd.Series, index: TYPE_INDEX, delta: int
) -> Tuple[int, int]:
    return _adjust_position(row, index, delta, "end")
