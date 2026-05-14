"""Typing"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# Pandas dataframe used in this library should have `RangeIndex` as index
TYPE_INDEX = int | np.int64


@dataclass
class Position:
    """Row/column position of a token in source code.

    Attributes
    ----------
    x : int
        Line number (1-based, matching Python's tokenize convention).
    y : int
        Column offset (0-based).
    """

    x: int
    y: int

    @classmethod
    def from_tuple(cls, pos: tuple[int, int]) -> Position:
        """Construct from a ``(row, col)`` tuple.

        Parameters
        ----------
        pos : tuple[int, int]
            ``(row, col)`` as produced by Python's tokenize module.

        Returns
        -------
        Position
        """
        assert isinstance(pos, tuple), type(pos)
        return cls(pos[0], pos[1])

    @classmethod
    def from_dict(cls, d: dict[str, int]) -> Position:
        """Construct from a dict with ``x`` and ``y`` keys.

        Parameters
        ----------
        d : dict[str, int]
            Must contain keys ``"x"`` and ``"y"``.

        Returns
        -------
        Position
        """
        return cls(d["x"], d["y"])

    @classmethod
    def auto(cls, d: tuple[int, int] | dict[str, int] | Position) -> Position:
        """Construct from any supported representation.

        Accepts a ``(row, col)`` tuple, a ``{"x": ..., "y": ...}`` dict, or
        an existing :class:`Position` instance (returned as-is).

        Parameters
        ----------
        d : tuple[int, int] | dict[str, int] | Position
            Source value to convert.

        Returns
        -------
        Position

        Raises
        ------
        TypeError
            If ``d`` is not one of the supported types.
        """
        if isinstance(d, tuple):
            return cls.from_tuple(d)
        if isinstance(d, dict):
            return cls.from_dict(d)
        if isinstance(d, Position):
            return d
        raise TypeError(type(d))
