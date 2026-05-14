"""Tokenize script"""

from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass
from token import tok_name
from tokenize import (
    FSTRING_END,
    FSTRING_MIDDLE,
    FSTRING_START,
    NAME,
    OP,
    STRING,
)
from typing import Any

import pandas as pd

from sqlfluff_py.typing import Position

_logger = logging.getLogger(__name__)


@dataclass
class Token:
    type: int
    string: str
    start: Position
    end: Position
    line: str

    @classmethod
    def from_indexable(cls, s: pd.Series | dict[str, Any]) -> Token:
        return cls(
            s["type"],
            s["string"],
            Position.auto(s["start"]),
            Position.auto(s["end"]),
            s["line"],
        )

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Token:
        return cls.from_indexable(d)

    @classmethod
    def from_series(cls, s: pd.Series) -> Token:
        return cls.from_indexable(s)

    def to_tuple(self) -> tuple[int, str, Position, Position, str]:
        return (self.type, self.string, self.start, self.end, self.line)


def _log_token(token: Token) -> None:
    _logger.debug(
        f"Appending token: ({tok_name[token.type]}, "
        f"{token.string.replace('\n', '\\n')})"
    )


def _validate_token(token: Token, prev_token: Token) -> None:
    assert (token.start.x, token.start.y) >= (
        prev_token.end.x,
        prev_token.end.y,
    ), (token.start, prev_token.end)


def retokenize(
    df: pd.DataFrame, pat: re.Pattern[str]
) -> tuple[pd.DataFrame, dict[str, str]]:
    """Retokenize script which is parsed to dataframe while replacing f-string
    expressions with numbered placeholders

    Returns the dataframe and a mapping of placeholder key -> original
    expression,
    e.g.
    {
        "__placeholder_0__": "table_name",
        "__placeholder_1__": "datetime.datetime.now(TZ)"
    }
    """
    _logger.debug("Retokenization started")
    tokens: list[Token] = []
    placeholder_map: dict[str, str] = {}

    is_fstring = False
    in_placeholder = False
    placeholder_expr = ""
    fstring_start: Position | None = None
    string = ""
    prev_name = ""

    row: pd.Series
    for _, row in df.iterrows():
        tok = Token.from_series(row)
        _logger.debug(tok)
        if is_fstring:
            _logger.debug(f"f-string token: {tok.string}")
            if tok.type == FSTRING_MIDDLE:
                string += tok.string
            elif tok.type == OP and tok.string == "{":
                in_placeholder = True
                placeholder_expr = ""
            elif tok.type == OP and tok.string == "}" and in_placeholder:
                in_placeholder = False
                key = f"__placeholder_{len(placeholder_map)}__"
                placeholder_map[key] = placeholder_expr
                string += key
            elif in_placeholder:
                placeholder_expr += tok.string

        if tok.type == NAME and tok.line.lstrip().startswith(row["string"]):
            prev_name = tok.string

        # f-string
        if tok.type == FSTRING_START and pat.search(prev_name) is not None:
            is_fstring = True
            fstring_start = tok.start
        elif tok.type == FSTRING_END:
            is_fstring = False
            in_placeholder = False
            if string:
                tok_string = string
                line = tok_string
            else:
                tok_string = tok.string
                line = tok.line
            start = fstring_start if fstring_start is not None else tok.start
            token = Token(STRING, tok_string, start, tok.end, line)
            _log_token(token)
            if tokens:
                prev_token = tokens[-1]
                _validate_token(token, prev_token)
            tokens.append(token)
            string = ""
            fstring_start = None
        else:
            if not is_fstring:
                token = Token.from_series(row)
                if tokens:
                    prev_token = tokens[-1]
                    _validate_token(token, prev_token)
                _log_token(token)
                tokens.append(token)

    _logger.debug("Retokenization finished")
    df = pd.DataFrame([asdict(_) for _ in tokens])
    for attr in ["start", "end"]:
        df[attr] = df.apply(lambda r: Position.auto(r[attr]), axis=1)
    return df, placeholder_map
