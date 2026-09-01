"""Tell an edited theme slot from one that still holds Microsoft's shipped value."""

from __future__ import annotations

# Each generation's six accents, complete: a partial set silently treats Microsoft's
# own colours as brand ones, and accent1/accent2 are exactly what a theme binds.
_OFFICE_2007 = ("4F81BD", "C0504D", "9BBB59", "8064A2", "4BACC6", "F79646")
_OFFICE_2013 = ("4472C4", "ED7D31", "A5A5A5", "FFC000", "5B9BD5", "70AD47")
_OFFICE_2024 = ("156082", "E97132", "196B24", "0F9ED5", "A02B93", "4EA72E")

_STOCK_ACCENTS = frozenset(_OFFICE_2007 + _OFFICE_2013 + _OFFICE_2024)


def is_stock_accent(hex_value: str) -> bool:
    """True when ``hex_value`` is an accent colour Microsoft ships and nobody edited."""
    return hex_value.strip().lstrip("#").upper() in _STOCK_ACCENTS
