"""Fix python script"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from io import BytesIO
from tokenize import (
    NAME,
    OP,
    STRING,
    tokenize,
    untokenize,
)

import pandas as pd
import sqlfluff

from sqlfluff_py.tokenize import retokenize
from sqlfluff_py.typing import TYPE_INDEX
from sqlfluff_py.utils import adjust_end, adjust_start, quote

_logger = logging.getLogger(__name__)


def _get_indent(df: pd.DataFrame, index: TYPE_INDEX, in_function: bool) -> int:
    """Get indent level"""
    # Get column location of variable (e.g. 4 for indent of 1)
    row = df.loc[(df.index < index) & (df["type"] == NAME)].iloc[-1]
    col_pos = row["start"][1]
    indent = int(col_pos / 4)
    # Add one more indent when string is within a function
    if in_function:
        indent += 1
    _logger.debug(f"Indent for variable `{row['string']}`: {indent}")
    return indent


def _fix_query(query: str, indent: int, dialect: str | None = None) -> str:
    """Call sqlfluff"""
    query = query.replace("'''", "").replace('"""', "")
    # Handle quotes for variables, using "<>" chars
    query = re.sub(r"\[\[placeholder_(.+?)\]\]", r"[<placeholder_\1>]", query)

    new_query: str = sqlfluff.fix(query, dialect)
    if new_query == query:
        _logger.info(f"Query was not modified: {query}")
        return query

    # Add indent to string
    new_query = "\n".join(
        [f"{'    ' * (indent + 1)}{_}" for _ in new_query.splitlines()]
    )
    _logger.debug(f"Query was fixed: {new_query}")
    return new_query


@dataclass
class QueryLength:

    original: int
    fixed: int

    @property
    def delta(self) -> int:
        return self.original - self.fixed


def get_script(
    script: str, pat: re.Pattern[str], dialect: str | None = None
) -> str:
    tokenized = tokenize(BytesIO(script.encode()).readline)
    df = retokenize(pd.DataFrame(list(tokenized)), pat)

    # Join w/ shifted df so each row can be inspected w/ the following one
    df_shifted = df.shift(-1).reset_index(drop=True)
    df_shifted.columns = [f"{_}_next" for _ in df.columns]
    df = df.join(df_shifted)

    # Identify variables that need fixing; variable NAME followed by "=" (OP)
    df_matched = df.loc[
        (df["type"] == NAME)
        & (df["type_next"] == OP)
        & (df["string"].str.contains(pat))
    ]
    if df_matched.empty:
        _logger.debug("No variables matched")
        return script

    row: pd.Series
    for _, row in df_matched.iterrows():
        string_row: pd.Series = df.loc[
            (df.index >= row.name) & (df["type"] == STRING)
        ].iloc[0]
        index = string_row.name
        assert isinstance(index, TYPE_INDEX), type(index)

        # Get indent
        row_variable_index = row.name
        variable_name = df.loc[row_variable_index]["string"]
        assert isinstance(row_variable_index, TYPE_INDEX), type(
            row_variable_index
        )
        in_function = (
            len(df.loc[(row_variable_index <= df.index) & (df.index <= index)])
            > 3
        )
        indent = _get_indent(df, row_variable_index, in_function)

        query = string_row["string"]
        _logger.debug(f"Fixing query: {query}")
        new_query = _fix_query(query, indent, dialect)
        new_query = quote(new_query, indent)
        _logger.debug(f"Result of sqlfluff: {new_query}")

        # Adjust start/end positions for following tokens
        ql = QueryLength(len(query.splitlines()), len(new_query.splitlines()))
        _logger.debug(f"Delta for {variable_name}: {ql}")
        if ql.delta != 0:
            df["start"] = df.apply(
                lambda r: adjust_start(r, index, ql.delta + 1), axis=1
            )
            df["end"] = df.apply(
                lambda r: adjust_end(r, index, ql.delta - 1), axis=1
            )

        # Replace query in tokenized result
        df.loc[index, "string"] = new_query

    # Rebuild tokens and make new script
    tokens = [
        # (r["type"], r["string"], r["start"], r["end"], r["line"])
        (r["type"], r["string"])
        for _, r in df.iterrows()
    ]
    for tok in tokens:
        _logger.debug(tok)

    df = pd.DataFrame(tokens)

    untokenized = untokenize(tokens)
    assert isinstance(untokenized, bytes)

    # Replace placeholders
    output = re.sub(r"\[placeholder_(.+?)\]", r"{\1}", untokenized.decode())
    # Quoted python variables
    output = re.sub(r"\[<placeholder_(.+?)>\]", r"[{\1}]", output)
    return output


__all__ = ["get_script"]
