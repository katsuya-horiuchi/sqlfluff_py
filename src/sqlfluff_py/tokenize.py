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
class Position:
    x: int
    y: int

    @classmethod
    def from_tuple(cls, pos: tuple[int, int]) -> Position:
        assert isinstance(pos, tuple), type(pos)
        return cls(pos[0], pos[1])

    @classmethod
    def from_dict(cls, d: dict[str, int]) -> Position:
        return cls(d["x"], d["y"])

    @classmethod
    def auto(cls, d: tuple[int, int] | dict[str, int]) -> Position:
        if isinstance(d, tuple):
            return cls.from_tuple(d)
        if isinstance(d, dict):
            return cls.from_dict(d)
        if isinstance(d, Position):
            return d
        raise TypeError(type(d))

    def __gt__(self, other: Position) -> bool:
        return (self.x == other.x and self.y > other.y) or (self.x > other.x)

    def __ge__(self, other: Position) -> bool:
        return self == other or self > other


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
    assert token.start >= prev_token.end, (token.start, prev_token.end)


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
        _logger.debug(tok)
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

        # f-string
        if tok.type == FSTRING_START and pat.search(prev_name) is not None:
            _logger.debug("Turning on is_fstring flag")
            is_fstring = True
        elif tok.type == FSTRING_END:
            _logger.debug("Turning off is_fstring flag")
            # breakpoint()
            is_fstring = False
            end = tok.end
            if string:
                tok_string = string
                end = Position(end.x, end.y + len(tok_string))
                line = tok_string
            else:
                tok_string = tok.string
                line = tok.line
            token = Token(STRING, tok_string, tok.start, end, line)
            _log_token(token)
            if tokens:
                prev_token = tokens[-1]
                token.start = prev_token.end
                _validate_token(token, prev_token)
            tokens.append(token)
            string = ""
        else:
            if not is_fstring:
                token = Token.from_series(row)
                if tokens:
                    prev_token = tokens[-1]
                    token.start = prev_token.end
                    _validate_token(token, prev_token)
                _log_token(token)
                tokens.append(token)
            else:
                pass
                # raise RuntimeError(token)

    _logger.debug("Retokenization finished")
    df = pd.DataFrame([asdict(_) for _ in tokens])
    for attr in ['start', 'end']:
        df[attr] = df.apply(lambda r: Position.auto(r[attr]), axis=1)
    return df
