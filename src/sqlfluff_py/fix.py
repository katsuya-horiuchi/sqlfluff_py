"""Fix python script"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from io import BytesIO
from token import tok_name
from tokenize import (
    NAME,
    OP,
    STRING,
    tokenize,
    untokenize,
)
from typing import Literal

import pandas as pd
import sqlfluff

from sqlfluff_py.tokenize import retokenize, Token
from sqlfluff_py.typing import Position
from sqlfluff_py.typing import TYPE_INDEX

_logger = logging.getLogger(__name__)


def _quote(query: str, indent: int) -> str:
    """Wrap a query string in Python string delimiters.

    Multiline queries are wrapped in triple quotes;
    single-line queries in double quotes.
    The f-prefix is added when the query contains placeholders.

    Parameters
    ----------
    query : str
        SQL query content without surrounding quotes.
    indent : int
        Indent level of the variable the query is assigned to. Controls the
        indentation of the closing triple-quote for multiline strings.

    Returns
    -------
    str
        The query wrapped in the appropriate Python string literal syntax.
    """
    f_prefix = "f" if "__placeholder_" in query else ""
    if "\n" in query:
        trailing_whitespace = f"{'    ' * indent}"
        query = f'{f_prefix}"""\n{query}\n{trailing_whitespace}"""'
    else:
        query = f'{f_prefix}"{query}"'
    return query


def _adjust_position(
    row: pd.Series, index: TYPE_INDEX, delta: int, attr: Literal["start", "end"]
) -> Position:
    """Shift the row component of a token position by delta.

    Tokens at or before ``index`` are left unchanged; only tokens that follow
    the modified STRING token need their row numbers updated.

    Parameters
    ----------
    row : pd.Series
        A single token row from the retokenized dataframe.
    index : TYPE_INDEX
        Dataframe index of the STRING token that was replaced.
    delta : int
        Number of rows to add to the position (negative to shift up).
    attr : {"start", "end"}
        Which position attribute to adjust.

    Returns
    -------
    Position
        The original position if ``row.name <= index``, otherwise a new
        Position with ``x`` shifted by ``delta``.
    """
    assert isinstance(row.name, TYPE_INDEX)
    pos_original: Position = Position.auto(row[attr])
    if row.name <= index:
        return pos_original
    pos = Position(pos_original.x + delta, pos_original.y)
    if pos != pos_original:
        _logger.debug(
            f"Position has been adjusted for {attr} for "
            f"token `{row['string']}`. "
            f"Original: {pos_original}. New: {pos}"
        )
    return pos


def _adjust_start(row: pd.Series, index: TYPE_INDEX, delta: int) -> Position:
    """Shift the start position row of a token after the replaced STRING.

    Parameters
    ----------
    row : pd.Series
        A single token row from the retokenized dataframe.
    index : TYPE_INDEX
        Dataframe index of the STRING token that was replaced.
    delta : int
        Number of rows to add (negative to shift up).

    Returns
    -------
    Position
        Adjusted start position.
    """
    return _adjust_position(row, index, delta, "start")


def _adjust_end(row: pd.Series, index: TYPE_INDEX, delta: int) -> Position:
    """Shift the end position row of a token after the replaced STRING.

    Parameters
    ----------
    row : pd.Series
        A single token row from the retokenized dataframe.
    index : TYPE_INDEX
        Dataframe index of the STRING token that was replaced.
    delta : int
        Number of rows to add (negative to shift up).

    Returns
    -------
    Position
        Adjusted end position.
    """
    return _adjust_position(row, index, delta, "end")


def _get_indent(row: pd.Series, in_function: bool) -> int:
    """Derive the indent level of a variable from its column position.

    Parameters
    ----------
    row : pd.Series
        The NAME token row for the variable.
    in_function : bool
        Whether the variable is inside a function body. Adds one extra
        indent level when ``True``.

    Returns
    -------
    int
        Indent level (0 = top-level, 1 = one block deep, etc.).
    """
    # Get column location of variable (e.g. 4 for indent of 1)
    tok = Token.from_series(row)
    col_pos = tok.start.y
    indent = int(col_pos / 4)
    # Add one more indent when string is within a function
    if in_function:
        indent += 1
    _logger.debug(f"Indent for variable `{tok.string}`: {indent}")
    return indent


def _fix_query(query: str, indent: int, dialect: str | None = None) -> str:
    """Format a SQL query string using sqlfluff and apply indentation.

    Parameters
    ----------
    query : str
        Raw SQL content extracted from the Python string token (no surrounding
        quotes).
    indent : int
        Indent level of the assignment variable. Each content line is indented
        one level deeper (``indent + 1``).
    dialect : str or None, optional
        sqlfluff dialect to use (e.g. ``"postgres"``, ``"ansi"``).

    Returns
    -------
    str
        Reformatted SQL with each line prefixed by the appropriate indentation.
        If sqlfluff makes no changes, the original content is returned stripped
        of leading newlines and trailing whitespace.
    """
    # Strip delimiters and the leading newline that follows the opening """.
    query = query.replace("'''", "").replace('"""', "").lstrip("\n")

    fixed_query: str = sqlfluff.fix(query, dialect)
    if fixed_query == query:
        _logger.debug("Query was not modified: %s", query)
    else:
        _logger.debug(
            "Query was modified. Before: %s | After: %s", query, fixed_query
        )

    # sqlfluff appends \n\n; strip trailing whitespace before re-wrapping
    content = fixed_query.rstrip()
    if "\n" not in content:
        return content
    return "\n".join(
        f"{'    ' * (indent + 1)}{line}" for line in content.splitlines()
    )


@dataclass
class _QueryLength:
    """Newline counts for a query before and after sqlfluff reformatting.

    Attributes
    ----------
    original : int
        Number of newlines in the original token string.
    fixed : int
        Number of newlines in the replacement string.
    """

    original: int
    fixed: int

    @property
    def delta(self) -> int:
        """Difference in line count (negative when the query shrank)."""
        return self.fixed - self.original


def _patch_token(
    df: pd.DataFrame, index: TYPE_INDEX, query: str, new_query: str
) -> None:
    """Write a reformatted query into the token dataframe and fix positions.

    Replaces the STRING token at ``index`` with ``new_query`` and adjusts all
    following token positions to stay consistent:

    - Row numbers of tokens after ``index`` are shifted when the line count
      changes.
    - The STRING token's own end position is updated for multiline tokens
      (``_adjust_position`` skips the token itself).
    - Column offsets of tokens on the closing line are shifted when the
      closing ``\"\"\"`` moves to a different column.

    Parameters
    ----------
    df : pd.DataFrame
        Retokenized token dataframe.
    index : TYPE_INDEX
        Dataframe index of the STRING token to replace.
    query : str
        Original token string (used to compute the line-count delta).
    new_query : str
        Replacement string produced by :func:`_fix_query` and :func:`quote`.
    """
    # Step 1: write the new string into the dataframe.
    df.loc[index, "string"] = new_query

    # Step 2: shift row numbers of all tokens that follow the replaced STRING.
    # When the query grows or shrinks, every subsequent token moves up or down
    # by the same number of lines.
    ql = _QueryLength(query.count("\n"), new_query.count("\n"))
    if ql.delta != 0:
        df["start"] = df.apply(
            lambda r: _adjust_start(r, index, ql.delta), axis=1
        )
        df["end"] = df.apply(lambda r: _adjust_end(r, index, ql.delta), axis=1)

    # Step 3: fix the STRING token's own end position for multiline tokens.
    # _adjust_position skips row.name <= index, so the token's end is never
    # updated by step 1; leaving it stale causes untokenize to emit \\\n.
    # Single-line tokens are skipped: their original end from retokenize is
    # correct, and updating it would push prev_col past the next token's
    # start, raising a ValueError in untokenize.
    if "\n" in new_query:
        original_end_col = Position.auto(df.loc[index, "end"]).y
        pos_start = Position.auto(df.loc[index, "start"])

        x_string = pos_start.x + new_query.count("\n")
        y_string = len(new_query.rsplit("\n", 1)[-1])
        df.at[index, "end"] = Position(x_string, y_string)

        # Step 4: fix column offsets on the closing line.
        # If the closing """ moved to a different column (e.g. over-indented
        # source had "    \"\"\"" but the fixed output has "\"\"\""), tokens
        # that follow on the same row still hold the original column and
        # untokenize inserts phantom spaces to bridge the gap.
        col_delta = y_string - original_end_col
        if col_delta != 0:
            mask_on_closing_row = df["start"].apply(
                lambda p: p.x == x_string and p.y >= original_end_col
            )
            mask = (df.index > index) & mask_on_closing_row
            df.loc[mask, "start"] = df.loc[mask, "start"].apply(
                lambda p: Position(p.x, p.y + col_delta)
            )
            df.loc[mask, "end"] = df.loc[mask, "end"].apply(
                lambda p: Position(p.x, p.y + col_delta)
            )


def _fix_variable(
    df: pd.DataFrame, row: pd.Series, dialect: str | None
) -> None:
    """Locate the SQL string for a matched variable, reformat it, and patch df.

    Parameters
    ----------
    df : pd.DataFrame
        Retokenized token dataframe (with lookahead columns joined in).
    row : pd.Series
        The NAME token row for the matched variable.
    dialect : str or None
        sqlfluff dialect passed to ``sqlfluff.fix``.
    """
    variable_name: str = row["string"]

    # Find string token for the given variable
    string_row: pd.Series = df.loc[
        (df.index >= row.name) & (df["type"] == STRING)
    ].iloc[0]
    index = string_row.name
    assert isinstance(index, TYPE_INDEX), type(index)

    # Get indent
    in_function: bool = (
        len(df.loc[(row.name <= df.index) & (df.index <= index)]) > 3
    )
    indent: int = _get_indent(row, in_function)

    query = string_row["string"]
    fixed_query = _fix_query(query, indent, dialect)
    fixed_query = _quote(fixed_query, indent)
    _patch_token(df, index, query, fixed_query)


def fix_script(
    script: str, pat: re.Pattern[str], dialect: str | None = None
) -> str:
    """Reformat SQL strings inside a Python script using sqlfluff.

    Tokenizes ``script``, finds every variable whose name matches ``pat``
    and whose value is a string literal, runs sqlfluff on the SQL content,
    and returns the script with the reformatted strings substituted in-place.

    Parameters
    ----------
    script : str
        Full source code of the Python script to process.
    pat : re.Pattern[str]
        Compiled regex pattern matched against variable names. Only variables
        whose names match are considered SQL queries.
    dialect : str or None, optional
        sqlfluff dialect passed to ``sqlfluff.fix`` (e.g. ``"postgres"``).

    Returns
    -------
    str
        The script with all matching SQL strings reformatted. Returned
        unchanged if no variables match ``pat``.
    """
    tokenized = tokenize(BytesIO(script.encode()).readline)
    df, placeholder_map = retokenize(pd.DataFrame(list(tokenized)), pat)

    # Join w/ shifted df so each row can be inspected w/ the following one
    df_shifted = df.shift(-1).reset_index(drop=True)
    assert len(df_shifted) == len(df)
    df_shifted.columns = [f"{_}_next" for _ in df.columns]
    df = df.join(df_shifted)

    # Identify variables that need fixing; variable NAME followed by "=" (OP)
    df_variables = df.loc[
        (df["type"] == NAME)
        & (df["type_next"] == OP)
        & (df["string_next"] == "=")
        & (df["string"].str.contains(pat))
    ]
    if df_variables.empty:
        _logger.debug("No variables matched")
        return script

    row: pd.Series
    for _, row in df_variables.iterrows():
        _fix_variable(df, row, dialect)

    # Rebuild tokens and make new script
    tokens = []
    for _, r in df.iterrows():
        tokens.append(
            (
                r["type"],
                r["string"],
                (r["start"].x, r["start"].y),
                (r["end"].x, r["end"].y),
                r["line"],
            )
        )

    untokenized = untokenize(tokens)
    assert isinstance(untokenized, bytes)

    output = untokenized.decode()
    for key, expr in placeholder_map.items():
        # Three brackets restore f-string expression replaced by placeholder
        output = output.replace(key, f"{{{expr}}}")
    return output


__all__ = ["fix_script"]
