"""Pure, theme-driven computations for chart rendering."""

from __future__ import annotations

from collections.abc import Iterable

from pptx.dml.color import RGBColor

_GRADIENT_LIGHTEN_FRACTION = 0.28  # how far toward white the second gradient stop sits
# Past this a label is unreadable at chart-label size, and the excess is float noise
# more often than authored precision. `decimals:` overrides it either way.
_DECIMALS_CAP = 4


# The units that read before the number. Everything else is a suffix.
_PREFIX_UNITS = frozenset({"$", "£", "€", "¥", "₹"})


def label_number_format(unit: str | None, *, thousands_sep: bool, decimals: int = 0) -> str | None:
    """The Excel number-format code for data labels, or ``None`` to leave the default.

    ``unit`` is quoted literally (``0"%"``) rather than Excel's ``%`` code, which
    multiplies the value by 100. That literal is why the places have to be written
    out: a quoted suffix cannot ride on a general format.
    """
    if not unit and not thousands_sep and not decimals:
        return None
    digits = "#,##0" if thousands_sep else "0"
    if decimals:
        digits = f"{digits}.{'0' * decimals}"
    if not unit:
        return digits
    if unit in _PREFIX_UNITS:
        return f'"{unit}"{digits}'
    return f'{digits}"{unit}"'


def label_text(value: float, *, unit: str | None, thousands_sep: bool, decimals: int) -> str:
    """A value as its data label prints it, for measuring the label rather than setting it."""
    digits = f"{value:,.{decimals}f}" if thousands_sep else f"{value:.{decimals}f}"
    if not unit:
        return digits
    return f"{unit}{digits}" if unit in _PREFIX_UNITS else f"{digits}{unit}"


def value_decimals(values: Iterable[float], *, cap: int = _DECIMALS_CAP) -> int:
    """Decimal places the labels need: the most any value carries, capped.

    ``repr`` is the shortest round-tripping form, so an authored ``11.2`` counts one
    place rather than seventeen. The cap catches values that arrived already noisy.
    """
    most = 0
    for value in values:
        text = repr(float(value))
        if "e" in text or "E" in text:
            continue
        places = len(text.partition(".")[2].rstrip("0"))
        most = max(most, places)
        if most >= cap:
            return cap
    return most


def lighten(color: RGBColor, fraction: float = _GRADIENT_LIGHTEN_FRACTION) -> RGBColor:
    """Blend ``color`` toward white by ``fraction`` — keeps a gradient reading
    as one hue with depth rather than two colours."""
    return RGBColor(*(round(c + (255 - c) * fraction) for c in color))
