"""Load a theme by name or path, binding semantic roles onto the referenced template.

Finding the file — the theme directory, ``DECKWRIGHT_THEME_DIR``, the packaged built-ins —
is :mod:`deckwright.theme.resolve`; its resolvers are re-exported here.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import yaml

from pf_core.log import get_logger

from deckwright.errors import ThemeError
from deckwright.theme import blocks
from deckwright.theme.blocks_motion import motion
from deckwright.theme.chartstyle import chart_style
from deckwright.theme.clrscheme import parse_color_scheme, parse_font_scheme, read_theme_xml
from deckwright.theme.defaults import (
    CANVAS_H_DEFAULT,
    CANVAS_W_DEFAULT,
    FACE_DEFAULT,
    HEADING_FACE_DEFAULT,
    LINE_WEIGHT_RUNG_DEFAULT,
    MIN_RUNG_DEFAULT,
    REFERENCE_HEIGHT_DEFAULT,
    MONO_DEFAULT,
    blank_presentation,
    default_ramp,
    default_theme,
)
from deckwright.theme.model import Theme
from deckwright.theme.palette import build_palette
from deckwright.theme.resolve import resolve_theme, theme_dir, theme_file  # noqa: F401 — re-exported
from deckwright.theme.scale import Scale
from deckwright.theme.surface import Surface, inherited_surface
from deckwright.utils.deck import open_presentation
from deckwright.utils.text import MEASURED_FAMILIES, measured

logger = get_logger(__name__)

_TYPE_KEYS = (
    "face",
    "heading_face",
    "mono",
    "reference_height",
    "ramp",
    "min_pt",
    "line_weight_pt",
)

_EMU_PER_INCH = 914400
# OOXML's references to a template's own fontScheme entries. Valid in a run's typeface
# attribute, never in a theme file: a theme names a face.
_SCHEME_REF = ("+mj-", "+mn-")


def load_theme(
    name_or_path: str | Path | None = None,
    *,
    slide_w: float = CANVAS_W_DEFAULT,
    slide_h: float = CANVAS_H_DEFAULT,
) -> Theme:
    """Read a theme and specialize the design system into its template.

    ``name_or_path`` is either a path to a theme YAML file, or a bare theme name —
    ``load_theme("base")``, ``load_theme("acme")`` — resolved through
    :func:`resolve_theme` exactly as a spec's ``theme:`` is.

    ``bind:`` maps semantic role names onto slots in the template's own
    ``clrScheme``, or onto literal ``RRGGBB`` values; every unbound role keeps its
    system default. With no ``template:`` only literals resolve, since there is no
    scheme to name a slot in.

    With no argument the built-in design system is returned, resolved onto a blank
    canvas of ``slide_w`` x ``slide_h`` inches.

    Raises:
        ThemeError: the name resolves to nothing, the file or its template is missing
            or unreadable, a key or role is unknown, a value is not the number or the
            mapping its key expects, a bind names a slot the template does not define,
            or a bind leaves a colour pair below WCAG AA.
    """
    if name_or_path is None:
        return default_theme(slide_w=slide_w, slide_h=slide_h)
    path = theme_file(name_or_path)
    try:
        raw: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except UnicodeDecodeError as e:
        raise ThemeError(f"{path.name} is not a text theme file: {path}") from e
    except yaml.YAMLError as e:
        raise ThemeError(f"invalid YAML in theme file {path}: {e}") from e
    if not isinstance(raw, dict):
        raise ThemeError(f"theme file {path} must contain a mapping at its top level")
    blocks.check_keys(raw, path=path)
    where = f"theme {path}"

    name = str(raw.get("name", path.stem))
    declared = str(raw.get("template", "")).strip()
    template: Path | None = None

    if declared:
        template = (path.parent / declared).resolve()
        if not template.is_file():
            raise ThemeError(f"template not found: {template} (referenced by {path})")
        prs = open_presentation(template)
    else:
        if raw.get("marks"):
            raise ThemeError(
                f"theme {name!r} declares 'marks:' but no 'template:' — mark media is "
                f"resolved beside the template or out of it; drop the marks or name "
                f"a template"
            )
        prs = blank_presentation(slide_w=slide_w, slide_h=slide_h)

    scale = Scale(slide_w=prs.slide_width / _EMU_PER_INCH, slide_h=prs.slide_height / _EMU_PER_INCH)

    surface: Surface | None = None
    if template is None:
        # No clrScheme to bind onto, so only literal colours resolve; with no bind at
        # all this reproduces DEFAULT_PALETTE exactly.
        roles, pairs = blocks.bind(
            blocks.mapping(raw.get("bind"), "bind", where=where), {}, theme_name=name
        )
        palette = build_palette(roles, pairs=pairs)
        major, minor = HEADING_FACE_DEFAULT, FACE_DEFAULT
    else:
        layout = _compose_layout(prs, raw.get("compose_layout"))
        theme_xml = read_theme_xml(layout.slide_master)
        major, minor = _scheme_faces(theme_xml, theme=name, template=template)
        roles, pairs = blocks.bind(
            blocks.mapping(raw.get("bind"), "bind", where=where),
            parse_color_scheme(theme_xml),
            theme_name=name,
        )
        palette = build_palette(roles, pairs=pairs)
        surface = inherited_surface(layout)

    type_cfg = blocks.mapping(raw.get("type"), "type", where=where)
    blocks.reject_unknown(type_cfg, _TYPE_KEYS, where=f"{where} 'type'")
    # A template's fontScheme routinely lags the face its slides really use, so an
    # explicit face: wins over it. major is the display face, minor the body face.
    face = _declared_face(type_cfg, "face", minor, theme=name)
    heading_face = _declared_face(type_cfg, "heading_face", major, theme=name)
    mono = _declared_face(type_cfg, "mono", MONO_DEFAULT, theme=name)
    # An unmeasured face is estimated with CEILING, which errs wide.
    for role, candidate in (("face", face), ("heading_face", heading_face)):
        if not measured(candidate):
            logger.warning(
                "theme_face_unmeasured",
                theme=name,
                role=role,
                face=candidate,
                measured=MEASURED_FAMILIES,
            )
    ramp = default_ramp(scale, heading_face=heading_face)
    reference_h = blocks.number(
        type_cfg.get("reference_height", REFERENCE_HEIGHT_DEFAULT),
        "type.reference_height",
        where=where,
        cast=float,
        expected="a canvas height in inches",
    )
    if reference_h <= 0:
        raise ThemeError(
            f"{where}: type.reference_height is {reference_h!r}; it is the canvas height the "
            f"ramp's point sizes are written for, so it must be above zero"
        )
    ramp.update(
        {
            name_: blocks.rung(
                name_,
                cfg,
                face=face,
                heading_face=heading_face,
                mono_face=mono,
                scale=scale,
                reference_height=reference_h,
            )
            for name_, cfg in blocks.mapping(type_cfg.get("ramp"), "type.ramp", where=where).items()
        }
    )

    theme = Theme(
        name=name,
        template=template,
        drop_template_slides=bool(raw.get("drop_template_slides", False)),
        palette=palette,
        scale=scale,
        face=face,
        heading_face=heading_face,
        mono=mono,
        ramp=ramp,
        min_pt=scale.pt(_rung(type_cfg, "min_pt", MIN_RUNG_DEFAULT, ref=reference_h, where=where)),
        grid=blocks.grid(
            blocks.mapping(raw.get("scale"), "scale", where=where), scale, where=where
        ),
        motion=motion(raw.get("motion"), path=path),
        marks=blocks.marks(blocks.mapping(raw.get("marks"), "marks", where=where), path=path),
        line_weight=scale.pt(
            _rung(
                type_cfg, "line_weight_pt", LINE_WEIGHT_RUNG_DEFAULT, ref=reference_h, where=where
            )
        ),
        chart=chart_style(blocks.mapping(raw.get("chart"), "chart", where=where), path=path),
        reserve=blocks.reserve(raw.get("reserve"), path=path),
        chrome=blocks.chrome(raw.get("chrome"), path=path),
        icons=blocks.icons(raw.get("icons"), path=path),
        compose_layout=(str(raw["compose_layout"]) if raw.get("compose_layout") else None),
        surface=surface,
        hash=_hash(path, template),
    )
    logger.info(
        "theme_loaded",
        theme=theme.name,
        template=str(template),
        roles=len(palette.roles),
        accents=len(palette.accents),
    )
    return theme


def _scheme_faces(theme_xml: bytes, *, theme: str, template: Path) -> tuple[str, str]:
    """The template's ``(major, minor)`` latin faces, or the built-in pair when it names none.

    ``conform`` reads the faces off the template's slides and skips a fontScheme with no
    usable latin entry, so the theme it writes must load past the same scheme.
    """
    try:
        return parse_font_scheme(theme_xml)
    except ThemeError as e:
        logger.warning(
            "theme_font_scheme_unusable",
            theme=theme,
            template=str(template),
            reason=str(e),
            using={"heading_face": HEADING_FACE_DEFAULT, "face": FACE_DEFAULT},
        )
        return HEADING_FACE_DEFAULT, FACE_DEFAULT


def _declared_face(type_cfg: dict[str, Any], key: str, fallback: str, *, theme: str) -> str:
    """A ``type:`` face name, with an OOXML fontScheme reference discarded for ``fallback``.

    ``+mj-lt`` and its siblings name a slot in a template's fontScheme, not a typeface:
    nothing can measure one, and a reader resolves it against whatever template it has.
    """
    declared = str(type_cfg.get(key) or "").strip()
    if not declared:
        return fallback
    if declared.lower().startswith(_SCHEME_REF):
        logger.warning(
            "theme_face_scheme_reference",
            theme=theme,
            key=f"type.{key}",
            token=declared,
            using=fallback,
            fix=f"re-adopt the template: deckwright conform <template>.pptx --adopt {theme}",
        )
        return fallback
    return declared


def _rung(type_cfg: dict[str, Any], key: str, default: float, *, ref: float, where: str) -> float:
    """A ``type:`` point size as its ratio to the reference canvas, or the system default."""
    if key not in type_cfg:
        return default
    pt = blocks.number(
        type_cfg[key], f"type.{key}", where=where, cast=float, expected="a point size"
    )
    return pt / ref


def _compose_layout(prs, prefer: str | None = None):
    """The layout the deck composes on — whose palette and surface the theme takes."""
    # Imported here, not at module scope: deckwright.layouts' package __init__ pulls in
    # compose and the registry, which import back through deckwright.theme.
    from deckwright.layouts.resolve import pick_compose_layout

    return pick_compose_layout(prs, prefer=prefer)


def _hash(theme_path: Path, template: Path | None) -> str:
    """Identity for cache keys — changes when either the YAML or the template changes."""
    h = hashlib.sha256()
    h.update(theme_path.read_bytes())
    if template is not None:
        h.update(template.read_bytes())
    return h.hexdigest()[:16]
