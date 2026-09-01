"""ChartStyle, and the parser for a theme file's ``chart:`` block."""

from __future__ import annotations

from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any

from deckwright.errors import ThemeError
from deckwright.utils.keys import unknown_field

_GRID_VALUES = ("none", "horizontal")
_LABEL_POSITIONS = ("outside_end", "inside_end", "none")
_MARKER_STYLE_VALUES = ("circle", "square", "diamond", "none")


@dataclass(frozen=True)
class ChartStyle:
    """Every aesthetic knob a chart renderer reads from ``theme.chart``."""

    gap_width: int = 60  # percent of bar width; python-pptx's plot.gap_width
    gradient: bool = False
    gradient_angle: float = 90.0  # degrees; python-pptx convention, 90 = top-to-bottom
    shadow: bool = False
    shadow_blur_pt: float = 4.0
    shadow_dist_pt: float = 3.0
    shadow_dir_deg: float = 45.0  # degrees, clockwise from 3 o'clock (OOXML outerShdw)
    shadow_alpha: float = 0.4  # 0.0 (transparent) to 1.0 (opaque)
    # PowerPoint draws its own tiny auto marker whatever we ask for, so there is no
    # faithful "off" — this is a deliberately visible baseline instead.
    marker_size: int = 8  # points, 2-72 (OOXML ST_MarkerSize)
    marker_style: str = "circle"
    grid: str = "horizontal"
    label_position: str = "outside_end"
    thousands_sep: bool = True  # group digits in data labels (#,##0)

    def __post_init__(self) -> None:
        if not 0 <= self.gap_width <= 500:
            raise ThemeError(f"chart gap_width must be 0-500, got {self.gap_width}")
        if self.shadow_blur_pt < 0:
            raise ThemeError(f"chart shadow_blur_pt must be >= 0, got {self.shadow_blur_pt}")
        if self.shadow_dist_pt < 0:
            raise ThemeError(f"chart shadow_dist_pt must be >= 0, got {self.shadow_dist_pt}")
        if not 0.0 <= self.shadow_alpha <= 1.0:
            raise ThemeError(f"chart shadow_alpha must be 0.0-1.0, got {self.shadow_alpha}")
        if not 2 <= self.marker_size <= 72:
            raise ThemeError(f"chart marker_size must be 2-72, got {self.marker_size}")
        if self.marker_style not in _MARKER_STYLE_VALUES:
            raise ThemeError(
                f"chart marker_style must be one of {', '.join(_MARKER_STYLE_VALUES)}, "
                f"got {self.marker_style!r}"
            )
        if self.grid not in _GRID_VALUES:
            raise ThemeError(
                f"chart grid must be one of {', '.join(_GRID_VALUES)}, got {self.grid!r}"
            )
        if self.label_position not in _LABEL_POSITIONS:
            raise ThemeError(
                f"chart label_position must be one of {', '.join(_LABEL_POSITIONS)}, "
                f"got {self.label_position!r}"
            )


#: Read off the dataclass so a default has exactly one home.
_FIELD_DEFAULTS: dict[str, Any] = {f.name: f.default for f in fields(ChartStyle)}
_CHART_KEYS = (
    "gap_width",
    "gradient",
    "gradient_angle",
    "shadow",
    "shadow_blur_pt",
    "shadow_dist_pt",
    "shadow_dir_deg",
    "shadow_alpha",
    "marker_size",
    "marker_style",
    "grid",
    "label_position",
    "thousands_sep",
)


def _chart_int(cfg: dict[str, Any], key: str, default: int, *, path: Path) -> int:
    raw = cfg.get(key, default)
    try:
        return int(raw)
    except (TypeError, ValueError) as e:
        raise ThemeError(f"theme {path}: chart.{key} must be an int, got {raw!r}") from e


def _chart_float(cfg: dict[str, Any], key: str, default: float, *, path: Path) -> float:
    raw = cfg.get(key, default)
    try:
        return float(raw)
    except (TypeError, ValueError) as e:
        raise ThemeError(f"theme {path}: chart.{key} must be a number, got {raw!r}") from e


def chart_style(cfg: dict[str, Any], *, path: Path) -> ChartStyle:
    """Build a :class:`ChartStyle` from a theme file's ``chart:`` block.

    Raises:
        ThemeError: the block names an unknown field or a value of the wrong type.
    """
    unknown = sorted(set(cfg) - set(_CHART_KEYS))
    if unknown:
        raise ThemeError(
            unknown_field(
                unknown[0], _CHART_KEYS, where=f"theme {path}", lead="chart block has unknown field"
            )
        )
    return ChartStyle(
        gap_width=_chart_int(cfg, "gap_width", _FIELD_DEFAULTS["gap_width"], path=path),
        gradient=bool(cfg.get("gradient", _FIELD_DEFAULTS["gradient"])),
        gradient_angle=_chart_float(
            cfg, "gradient_angle", _FIELD_DEFAULTS["gradient_angle"], path=path
        ),
        shadow=bool(cfg.get("shadow", _FIELD_DEFAULTS["shadow"])),
        shadow_blur_pt=_chart_float(
            cfg, "shadow_blur_pt", _FIELD_DEFAULTS["shadow_blur_pt"], path=path
        ),
        shadow_dist_pt=_chart_float(
            cfg, "shadow_dist_pt", _FIELD_DEFAULTS["shadow_dist_pt"], path=path
        ),
        shadow_dir_deg=_chart_float(
            cfg, "shadow_dir_deg", _FIELD_DEFAULTS["shadow_dir_deg"], path=path
        ),
        shadow_alpha=_chart_float(cfg, "shadow_alpha", _FIELD_DEFAULTS["shadow_alpha"], path=path),
        marker_size=_chart_int(cfg, "marker_size", _FIELD_DEFAULTS["marker_size"], path=path),
        marker_style=str(cfg.get("marker_style", _FIELD_DEFAULTS["marker_style"])),
        grid=str(cfg.get("grid", _FIELD_DEFAULTS["grid"])),
        label_position=str(cfg.get("label_position", _FIELD_DEFAULTS["label_position"])),
        thousands_sep=bool(cfg.get("thousands_sep", _FIELD_DEFAULTS["thousands_sep"])),
    )
