"""The built-in design system: a complete theme that needs no template.

Every value is canvas-relative, so a change of slide size is a no-op. A template
specializes this; it never supplies it.
"""

from __future__ import annotations

import hashlib

from pptx import Presentation as new_presentation
from pptx.oxml.ns import qn
from pptx.presentation import Presentation
from pptx.util import Inches

from deckwright.theme.chartstyle import ChartStyle
from deckwright.theme.model import Theme, TypeStyle
from deckwright.theme.palette import AUTO_INK, Palette, build_palette
from deckwright.theme.scale import Grid, Scale

CANVAS_W_DEFAULT = 13.333
CANVAS_H_DEFAULT = 7.5

_EMU_PER_INCH = 914400

DEFAULT_ROLES: dict[str, str] = {
    "page": "FFFFFF",
    "ink": "1A1D21",
    "muted": "5F6672",
    "line": "E3E6EA",
    "surface": "F2F4F7",
    "surface-ink": "1A1D21",
    "inverse": "12161B",
    "inverse-ink": "FFFFFF",
    "accent-1": "1F5FA8",
    "accent-2": "0F6E63",
    "accent-3": "A8431C",
    "accent-4": "6A3FA0",
}

DEFAULT_ACCENTS: tuple[str, ...] = ("accent-1", "accent-2", "accent-3", "accent-4")

DEFAULT_PAIRS: dict[str, tuple[str, str]] = {
    "page": ("ink", "page"),
    "page-muted": ("muted", "page"),
    "surface": ("surface-ink", "surface"),
    "inverse": ("inverse-ink", "inverse"),
    **{name: (AUTO_INK, name) for name in DEFAULT_ACCENTS},
}

DEFAULT_PALETTE: Palette = build_palette(DEFAULT_ROLES, pairs=DEFAULT_PAIRS)

FACE_DEFAULT = "Helvetica"
HEADING_FACE_DEFAULT = "Helvetica"
MONO_DEFAULT = "Courier New"

_BODY_RUNG = 2.13
_RATIO = 1.25
# A kicker is bold and set in caps; a caption is not, so it takes its own step.
_STEPS = {
    "kicker": -1.0,
    "caption": -0.5,
    "body": 0.0,
    "lead": 1.0,
    "subtitle": 1.0,
    "head": 2.0,
    "title": 3.0,
    "stat": 3.5,
    "display": 4.0,
    "hero": 5.0,
}
_BOLD = frozenset({"kicker", "head", "title", "stat", "display", "hero"})
_HEADING = frozenset({"subtitle", "title", "stat", "display", "hero"})

DEFAULT_RAMP: dict[str, float] = {
    name: round(_BODY_RUNG * _RATIO**step, 4) for name, step in _STEPS.items()
}

# The canvas a theme's point sizes are written for: the 16:9 default.
REFERENCE_HEIGHT_DEFAULT = 7.5
MIN_RUNG_DEFAULT = 1.40
LINE_WEIGHT_RUNG_DEFAULT = 0.30


def default_ramp(scale: Scale, *, heading_face: str = HEADING_FACE_DEFAULT) -> dict[str, TypeStyle]:
    """The built-in type ramp bound to a canvas."""
    return {
        name: TypeStyle(
            rung=rung,
            scale=scale,
            bold=name in _BOLD,
            face=heading_face if name in _HEADING else None,
        )
        for name, rung in DEFAULT_RAMP.items()
    }


# No universal margin exists, so the default sits low and a binding overrides it.
_MARGIN_X_FRAC = 0.055
_MARGIN_Y_FRAC = 0.060
_GUTTER_FRAC = 0.014
_BODY_TOP_FRAC = 0.22
_COLUMNS = 12
# The vertical divisor a placement's `rows: {from: 1, to: 7}` indexes.
_ROWS = 12


def default_grid(scale: Scale) -> Grid:
    """The built-in column grid, its margins fractions of the canvas."""
    return Grid(
        scale=scale,
        top_frac=_MARGIN_Y_FRAC,
        right_frac=_MARGIN_X_FRAC,
        bottom_frac=_MARGIN_Y_FRAC,
        left_frac=_MARGIN_X_FRAC,
        columns=_COLUMNS,
        rows=_ROWS,
        gutter_frac=_GUTTER_FRAC,
        body_top_frac=_BODY_TOP_FRAC,
    )


DEFAULT_CHART = ChartStyle()


def blank_presentation(
    *, slide_w: float = CANVAS_W_DEFAULT, slide_h: float = CANVAS_H_DEFAULT
) -> Presentation:
    """An empty presentation at the given canvas size in inches — no template."""
    prs = new_presentation()
    prs.slide_width, prs.slide_height = Inches(slide_w), Inches(slide_h)
    # The stock template's `type` names 4:3 and the setters leave it behind.
    sld_sz = prs._element.find(qn("p:sldSz"))
    if sld_sz is not None and "type" in sld_sz.attrib:
        del sld_sz.attrib["type"]
    return prs


def default_theme(*, slide_w: float = CANVAS_W_DEFAULT, slide_h: float = CANVAS_H_DEFAULT) -> Theme:
    """The built-in design system resolved onto a blank canvas."""
    scale = Scale(slide_w=Inches(slide_w) / _EMU_PER_INCH, slide_h=Inches(slide_h) / _EMU_PER_INCH)
    return Theme(
        name="default",
        template=None,
        drop_template_slides=False,
        palette=DEFAULT_PALETTE,
        scale=scale,
        face=FACE_DEFAULT,
        heading_face=HEADING_FACE_DEFAULT,
        mono=MONO_DEFAULT,
        ramp=default_ramp(scale),
        min_pt=scale.pt(MIN_RUNG_DEFAULT),
        grid=default_grid(scale),
        line_weight=scale.pt(LINE_WEIGHT_RUNG_DEFAULT),
        chart=DEFAULT_CHART,
        hash=_identity(scale),
    )


def _identity(scale: Scale) -> str:
    """Cache key — changes when the system or the canvas changes."""
    h = hashlib.sha256()
    h.update(
        repr(
            (
                sorted(DEFAULT_ROLES.items()),
                sorted(DEFAULT_RAMP.items()),
                _MARGIN_X_FRAC,
                _MARGIN_Y_FRAC,
                _GUTTER_FRAC,
                _BODY_TOP_FRAC,
                _COLUMNS,
                round(scale.slide_w, 4),
                round(scale.slide_h, 4),
            )
        ).encode()
    )
    return h.hexdigest()[:16]
