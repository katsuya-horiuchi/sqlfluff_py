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


_logger = logging.getLogger(__name__)

TYPE_POS = tuple[int, int]


@dataclass
class Token:
    type: int
    string: str
    start: TYPE_POS
    end: TYPE_POS
    line: str

    @classmethod
    def from_indexable(cls, s: pd.Series | dict[str, Any]) -> Token:
        return cls(s["type"], s["string"], s["start"], s["end"], s["line"])

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Token:
        return cls.from_indexable(d)

    @classmethod
    def from_series(cls, s: pd.Series) -> Token:
        return cls.from_indexable(s)

    def to_tuple(self) -> tuple[int, str, TYPE_POS, TYPE_POS, str]:
        return (self.type, self.string, self.start, self.end, self.line)


def _log_token(token: Token) -> None:
    _logger.debug(
        f"Appending token: ({tok_name[token.type]}, "
        f"{token.string.replace('\n', '\\n')})"
    )


def _validate_token(token: Token, prev_token: Token) -> None:
    assert prev_token.start[0] <= token.start[0]


def retokenize(df: pd.DataFrame, pat: re.Pattern[str]) -> pd.DataFrame:
    """Retokenize while replacing variables within f-string with placeholder"""

    _logger.debug("Retokenization started")
    tokens: list[Token] = []

    is_fstring = False
    string = ""
    prev_name = ""

    row: pd.Series
    for _, row in df.iterrows():
        tok = Token.from_series(row)
        if is_fstring:
            _logger.debug(f"f-string token: {tok.string}")
            if tok.type == OP and tok.string == "{":
                string += "[placeholder_"
            if tok.type == FSTRING_MIDDLE:
                string += tok.string
            if tok.type == OP and tok.string == "}":
                string += "]"
            if tok.type == NAME:
                string += tok.string

        if tok.type == NAME and tok.line.startswith(row["string"]):
            prev_name = tok.string

        if tok.type == FSTRING_START and pat.search(prev_name) is not None:
            is_fstring = True
        elif tok.type == FSTRING_END:
            is_fstring = False
            end = tok.end
            if string:
                tok_string = string
                end = (end[0], end[1] + len(tok_string))
                line = tok_string
            else:
                tok_string = tok.string
                line = tok.line
            token = Token(STRING, tok_string, tok.start, end, line)
            _log_token(token)
            if tokens:
                _validate_token(token, tokens[-1])
            tokens.append(token)
            string = ""
        else:
            if not is_fstring:
                token = Token.from_series(row)
                _log_token(token)
                if tokens:
                    _validate_token(token, tokens[-1])
                tokens.append(token)

    _logger.debug("Retokenization finished")
    return pd.DataFrame([asdict(_) for _ in tokens])
