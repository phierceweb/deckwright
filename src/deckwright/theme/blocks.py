"""One parser per block of a theme YAML file, plus the top-level key vocabulary.

``load.py`` reads the file and assembles the :class:`~deckwright.theme.model.Theme`;
everything that turns one YAML block into a value object lives here.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from math import isfinite
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar

from pf_core.log import get_logger

from deckwright.errors import LayoutError, ThemeError
from deckwright.theme.defaults import (
    _BOLD as _RAMP_BOLD,
    _HEADING as _RAMP_HEADING,
    DEFAULT_PAIRS,
    DEFAULT_ROLES,
    default_grid,
)
from deckwright.theme.model import TypeStyle
from deckwright.theme.palette import AUTO_INK
from deckwright.theme.scale import Grid, Scale
from deckwright.utils.spans import percent
from deckwright.theme.stock import is_stock_accent

if TYPE_CHECKING:
    from deckwright.layouts.chrome import ChromeField
    from deckwright.layouts.place import Reserved

logger = get_logger(__name__)

_Num = TypeVar("_Num", int, float)

_ACCENT_ROLE = re.compile(r"^accent-([1-9][0-9]*)$")
_HEX = re.compile(r"^#?[0-9A-Fa-f]{6}$")
# A mark decorates a painted backdrop, and only 'inverse' paints one — a page slide
# keeps the master's own surface, so layouts/compose.py never looks up any other name.
_MARK_NAMES = ("inverse",)
_RESERVE_KEYS = ("name", "poly")
# A rung's `face:` names one of the theme's own faces by role, in the order rung()
# passes them; anything else is a literal typeface.
_FACE_ALIASES = ("body", "heading", "mono")
_KNOWN_KEYS = frozenset(
    {
        "name",
        "template",
        "compose_layout",
        "drop_template_slides",
        "bind",
        "scale",
        "type",
        "marks",
        "reserve",
        "chart",
        "chrome",
        "icons",
        "motion",
    }
)
_REPLACED_KEYS = {
    "grid": "'grid' was replaced by 'scale' (margins and gutter are now fractions of the canvas)",
    "roles": "'roles' was replaced by 'bind', which maps semantic role names onto template slots",
    "overrides": "'overrides' was replaced by 'bind'; an unbound role keeps the "
    "design system's default",
    "compose_on": "'compose_on' is gone — the compiler picks the emptiest layout "
    "across every master",
    "series_colors": "'series_colors' is gone — series cycle the palette's accent roles",
    "safe_zones": "'safe_zones' is gone — use 'reserve': polygons in fractions of the "
    "canvas, applying to every slide",
}


def reject_unknown(cfg: dict[str, Any], known: tuple[str, ...], *, where: str) -> None:
    """Refuse a key the loader would not read.

    A typo in a nested block is otherwise silent: the value is dropped and the default
    stands, so a theme reads as if it were honoured.
    """
    unknown = sorted(set(cfg) - set(known))
    if unknown:
        raise ThemeError(
            f"{where}: unknown key {unknown[0]!r}; known keys: {', '.join(sorted(known))}"
        )


def check_keys(raw: dict[str, Any], *, path: Path) -> None:
    """Reject removed keys by name, and anything the loader does not read."""
    for key, note in _REPLACED_KEYS.items():
        if key in raw:
            raise ThemeError(f"theme {path}: {note}")
    unknown = sorted(set(raw) - _KNOWN_KEYS)
    if unknown:
        raise ThemeError(
            f"theme file {path} has unknown top-level key {unknown[0]!r}; "
            f"known keys: {', '.join(sorted(_KNOWN_KEYS))}"
        )
    if "min_size" in mapping(raw.get("type"), "type", where=f"theme {path}"):
        raise ThemeError(
            f"theme {path}: key 'type.min_size' was replaced by 'min_pt' "
            f"(points per inch of canvas height)"
        )


def bind(
    cfg: dict[str, Any], scheme: dict[str, str], *, theme_name: str
) -> tuple[dict[str, str], dict[str, tuple[str, str]]]:
    """Layer explicit role -> template-slot bindings over the system defaults.

    A value is a slot name, or a literal ``RRGGBB`` — a template's real surface need
    not be in its ``clrScheme`` at all. An accent bound to a slot still holding
    Microsoft's shipped value is ignored, keeping the built-in accent; a literal is
    the author's own choice and is kept whatever it happens to equal.

    ``scheme`` is empty for a theme with no ``template:``, which makes a slot name
    unresolvable — only literals bind.
    """
    roles = dict(DEFAULT_ROLES)
    pairs = dict(DEFAULT_PAIRS)
    for key, value in cfg.items():
        role, slot = str(key), str(value)
        accent = _ACCENT_ROLE.match(role)
        if role not in DEFAULT_ROLES and not accent:
            raise ThemeError(
                f"theme {theme_name!r} binds unknown role {role!r}; known roles: "
                f"{', '.join(sorted(DEFAULT_ROLES))} (plus accent-N)"
            )
        literal = bool(_HEX.match(slot))
        if literal:
            resolved = slot.lstrip("#").upper()
        elif not scheme:
            raise ThemeError(
                f"theme {theme_name!r} binds {role!r} to {slot!r}, which reads as a "
                f"template slot name, but the theme names no 'template:' — give a "
                f"literal RRGGBB, or name a template to bind its slots"
            )
        else:
            try:
                resolved = scheme[slot]
            except KeyError:
                raise ThemeError(
                    f"theme {theme_name!r} binds {role!r} to unknown template slot "
                    f"{slot!r}; template defines: {', '.join(sorted(scheme))} "
                    f"(or give a literal RRGGBB)"
                ) from None
        # Only a slot can be stock: an untouched slot means the brand set no accent
        # there, while a literal is what the author typed.
        if accent and not literal and is_stock_accent(resolved):
            logger.warning(
                "stock_accent_ignored", theme=theme_name, role=role, slot=slot, value=resolved
            )
            continue
        roles[role] = resolved
        if accent:
            pairs[role] = (AUTO_INK, role)
    return roles, pairs


def number(value: Any, key: str, *, where: str, cast: Callable[[Any], _Num], expected: str) -> _Num:
    """A numeric scalar out of theme config, naming the key that will not convert.

    ``.inf`` and ``.nan`` are YAML floats that cast without complaint, then divide and
    round into nonsense pages later — they are refused here with everything else. The
    weighing is inside the ``try``: an integer past a float's range casts, then raises
    ``OverflowError`` on being weighed.
    """
    bad = ThemeError(f"{where}: {key} is {expected}, got {value!r}")
    try:
        out = cast(value)
        finite = isfinite(out)
    except (TypeError, ValueError, OverflowError):
        raise bad from None
    if not finite:
        raise bad
    return out


def mapping(value: Any, key: str, *, where: str) -> dict[str, Any]:
    """A block of theme config as a mapping, naming the key that is not one."""
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ThemeError(f"{where}: {key} is a mapping of settings, got {value!r}")
    return value


def rung(
    name: str,
    cfg: Any,
    *,
    face: str,
    heading_face: str,
    mono_face: str,
    scale: Scale,
    reference_height: float,
) -> TypeStyle:
    """Build one ramp rung from the point size it is written as.

    A theme states ``pt: 14`` — the size on a canvas ``reference_height`` inches tall;
    what is kept is the ratio, so the ramp scales with the canvas. ``face:`` names one of
    the theme's own faces by role — ``body``, ``heading``, ``mono`` — and anything else is
    a literal typeface.
    """
    if not isinstance(cfg, dict):
        raise ThemeError(f"type ramp entry {name!r} must be a mapping")
    for gone, why in (("size", "point size"), ("rung", "points per inch of canvas height")):
        if gone in cfg:
            raise ThemeError(
                f"type ramp entry {name!r}: {gone!r} ({why}) was replaced by 'pt' — "
                f"the size at the theme's reference_height"
            )
    where = f"type ramp entry {name!r}"
    if "pt" not in cfg:
        raise ThemeError(f"{where} needs a 'pt'")
    pt = number(cfg["pt"], "pt", where=where, cast=float, expected="a point size")
    alias = cfg.get("face")
    # An entry that names only a size keeps the design system's weight and face for its
    # rung: `title: {pt: 34}` resizes the title, it does not quietly un-bold it.
    if alias is None:
        resolved = heading_face if name in _RAMP_HEADING else None
    else:
        faces = dict(zip(_FACE_ALIASES, (face, heading_face, mono_face), strict=True))
        wanted = str(alias)
        resolved = faces.get(wanted, wanted)
        if wanted not in faces and wanted.casefold() in faces:
            logger.warning(
                "theme_ramp_face_alias_case", rung=name, face=wanted, aliases=_FACE_ALIASES
            )
    return TypeStyle(
        rung=pt / reference_height,
        scale=scale,
        bold=bool(cfg.get("bold", name in _RAMP_BOLD)),
        italic=bool(cfg.get("italic", False)),
        face=resolved or None,
    )


_SCALE_KEYS = ("margin", "columns", "rows", "gutter", "body_top")
_MARGIN_KEYS = ("top", "right", "bottom", "left")


def grid(cfg: dict[str, Any], scale: Scale, *, where: str = "theme") -> Grid:
    """The theme's grid; anything the ``scale:`` block omits falls to the built-in one."""
    base = default_grid(scale)
    reject_unknown(cfg, _SCALE_KEYS, where=f"{where} 'scale'")
    margin = mapping(cfg.get("margin"), "margin", where=f"{where} 'scale'")
    reject_unknown(margin, _MARGIN_KEYS, where=f"{where} 'scale.margin'")

    def frac(block: dict[str, Any], key: str, fallback: float) -> float:
        """A percent of the canvas, or the built-in grid's value where unstated."""
        if key not in block:
            return fallback
        return percent(block[key], key, where="theme 'scale'", error=ThemeError)

    return Grid(
        scale=scale,
        top_frac=frac(margin, "top", base.top_frac),
        right_frac=frac(margin, "right", base.right_frac),
        bottom_frac=frac(margin, "bottom", base.bottom_frac),
        left_frac=frac(margin, "left", base.left_frac),
        columns=number(
            cfg.get("columns", base.columns),
            "columns",
            where="theme 'scale'",
            cast=int,
            expected="a whole number of columns",
        ),
        rows=number(
            cfg.get("rows", base.rows),
            "rows",
            where="theme 'scale'",
            cast=int,
            expected="a whole number of rows",
        ),
        gutter_frac=frac(cfg, "gutter", base.gutter_frac),
        body_top_frac=frac(cfg, "body_top", base.body_top_frac),
    )


def marks(cfg: dict[str, Any], *, path: Path) -> dict[str, Any]:
    """Theme art, keyed by the background it decorates."""
    unknown = sorted(set(cfg) - set(_MARK_NAMES))
    if unknown:
        raise ThemeError(
            f"theme {path}: mark {unknown[0]!r} names no painted backdrop, so nothing "
            f"would ever lay it down; a mark's name is the background it decorates — "
            f"known marks: {', '.join(_MARK_NAMES)}"
        )
    for name, value in cfg.items():
        if not isinstance(value, dict) or not value.get("media"):
            raise ThemeError(
                f"theme {path}: mark {name!r} needs a mapping with a 'media:' naming an "
                f"image file, got {value!r}"
            )
    return cfg


def icons(cfg: Any, *, path: Path) -> Path | None:
    """The theme's own icon directory, resolved beside the theme file.

    Searched before the shipped set, so a brand overrides a name without renaming
    anything in the decks.
    """
    if cfg is None:
        return None
    directory = (path.parent / str(cfg)).resolve()
    if not directory.is_dir():
        raise ThemeError(
            f"theme {path}: icons directory not found: {directory} — 'icons:' names a "
            f"directory of .svg files beside the theme, not an icon"
        )
    return directory


def chrome(cfg: Any, *, path: Path) -> dict[str, ChromeField]:
    """The theme's title treatment: where each chrome line sits and how it is set.

    Every value is a fraction of the canvas plus ``align``/``anchor``. A field the
    theme omits stacks from the top margin at the content width.
    """
    # Imported here for the same reason as _region below.
    from deckwright.layouts.chrome import chrome_field

    if cfg is None:
        return {}
    if not isinstance(cfg, dict):
        raise ThemeError(
            f"theme {path}: 'chrome' is a mapping of chrome field to its treatment, got {cfg!r}"
        )
    out: dict[str, ChromeField] = {}
    for key, entry in cfg.items():
        try:
            out[str(key)] = chrome_field(entry, name=str(key))
        except LayoutError as e:
            raise ThemeError(f"theme {path}: {e}") from None
    return out


def reserve(cfg: Any, *, path: Path) -> tuple[Reserved, ...]:
    """Every reserved region the theme declares, as polygons in canvas fractions."""
    if cfg is None:
        return ()
    if not isinstance(cfg, list):
        raise ThemeError(
            f"theme {path}: 'reserve' is a list of regions, each a mapping with a 'name' "
            f"and a 'poly', got {cfg!r}"
        )
    return tuple(_region(entry, path=path) for entry in cfg)


def _region(cfg: Any, *, path: Path) -> Reserved:
    # Imported here, not at module scope: layouts.place reads deckwright.theme.model, so
    # a module-scope import would reach back into this package while it is still loading.
    from deckwright.layouts.place import Reserved

    if not isinstance(cfg, dict):
        raise ThemeError(
            f"theme {path}: each 'reserve' entry is a mapping with a 'name' and a "
            f"'poly', got {cfg!r}"
        )
    name = str(cfg.get("name", "unnamed"))
    where = f"theme {path}: reserved region {name!r}"
    if "applies_to" in cfg:
        raise ThemeError(
            f"{where}: 'applies_to' is gone — a slide has no layout to scope "
            f"a region to; every region applies to every slide"
        )
    unknown = sorted(set(cfg) - set(_RESERVE_KEYS))
    if unknown:
        raise ThemeError(
            f"{where}: unknown key {unknown[0]!r}; known keys: {', '.join(_RESERVE_KEYS)}"
        )
    poly = cfg.get("poly")
    if not isinstance(poly, list):
        raise ThemeError(
            f"{where}: needs a 'poly' list of {{x, y}} points in percents of the canvas"
        )
    return Reserved(name=name, poly=tuple(_point(p, where=where) for p in poly))


def _point(value: Any, *, where: str) -> tuple[float, float]:
    if isinstance(value, (list, tuple)):
        raise ThemeError(
            f"{where}: a 'poly' point is keyed — write {{x: 78%, y: 0%}}, not {value!r}"
        )
    if not isinstance(value, dict) or set(value) != {"x", "y"}:
        raise ThemeError(
            f"{where}: every 'poly' point is an {{x, y}} mapping in percents of the "
            f"canvas, got {value!r}"
        )
    return (
        percent(value["x"], "poly.x", where=where, error=ThemeError),
        percent(value["y"], "poly.y", where=where, error=ThemeError),
    )
