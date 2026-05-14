import re
from io import BytesIO
from tokenize import STRING, tokenize

import pandas as pd

from sqlfluff_py.tokenize import retokenize
from sqlfluff_py.typing import Position


def _df(code: str) -> pd.DataFrame:
    # Adding b'\n' is necessary to simulate line ending
    return pd.DataFrame(list(tokenize(BytesIO(code.encode() + b"\n").readline)))


def test_retokenize_plain_string() -> None:
    df_result, placeholder_map = retokenize(
        _df('sql = "SELECT 1"'), re.compile("sql")
    )
    assert placeholder_map == {}
    df_strings = df_result[df_result["type"] == STRING]
    assert df_strings.iloc[0]["string"] == '"SELECT 1"'


def test_retokenize_simple_fstring() -> None:
    df_result, placeholder_map = retokenize(
        _df('sql = f"select {col}"'), re.compile("sql")
    )
    df_strings = df_result[df_result["type"] == STRING]
    assert len(df_strings) == 1
    assert df_strings.iloc[0]["string"] == "select __placeholder_0__"
    assert placeholder_map == {"__placeholder_0__": "col"}


def test_retokenize_no_match() -> None:
    # variable name doesn't match pattern → no placeholder substitution
    _, placeholder_map = retokenize(
        _df('query = f"select {col}"'), re.compile("sql")
    )
    assert placeholder_map == {}


def test_retokenize_multiple_placeholders() -> None:
    df_result, placeholder_map = retokenize(
        _df('sql = f"select {col} from {table}"'), re.compile("sql")
    )
    content = df_result[df_result["type"] == STRING].iloc[0]["string"]
    assert content == "select __placeholder_0__ from __placeholder_1__"
    assert placeholder_map["__placeholder_0__"] == "col"
    assert placeholder_map["__placeholder_1__"] == "table"


def test_retokenize_complex_expression() -> None:
    # full attribute-access + call expression inside {}
    df_result, placeholder_map = retokenize(
        _df('sql = f"select {obj.method(arg)}"'), re.compile("sql")
    )
    assert placeholder_map["__placeholder_0__"] == "obj.method(arg)"


def test_retokenize_fstring_start_position() -> None:
    # synthetic STRING token should start where the f" starts, not the content
    code = 'sql = f"select {col}"'
    df_result, _ = retokenize(_df(code), re.compile("sql"))
    df_strings = df_result[df_result["type"] == STRING]
    start = df_strings.iloc[0]["start"]
    # "sql = " is 6 chars → f" starts at column 6
    assert start.y == 6
