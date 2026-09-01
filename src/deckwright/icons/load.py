"""Find an icon by name and read the geometry out of it.

An icon is an ``.svg`` file named for what it depicts. One set ships: the vendored
Material Symbols, packed into ``glyphs/material/glyphs.zip`` and read out of that
archive (:mod:`deckwright.icons.vendor` builds and checks it), reached under its own
names, a hyphenated spelling of them, and the tables in :mod:`deckwright.icons.aliases`.

Config (env, read at call time, so ``.env`` changes take effect between runs):

- ``DECKWRIGHT_ICON_DIR`` — a directory searched before the theme's own and the shipped set.
"""

from __future__ import annotations

import difflib
import functools
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path

from lxml import etree


from deckwright.errors import SpecError
from deckwright.icons.aliases import ALIASES, OVERRIDES
from deckwright.icons.path import parse, to_drawingml
from deckwright.utils.env import env_str
from deckwright.utils.xml import fromstring as parse_xml

_SVG = "{http://www.w3.org/2000/svg}"
_ICON_DIR_ENV_VAR = "DECKWRIGHT_ICON_DIR"
# A deck may write either spelling: hyphens are normalised to the vendored underscores.
_NAME = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
_SUGGESTIONS = 4

VENDORED = Path(__file__).parent / "glyphs" / "material"
"""Where the shipped set lives — the bundle, its licence and its provenance."""

BUNDLE = VENDORED / "glyphs.zip"
"""The set that ships with deckwright, so ``icon:`` works before anything is configured."""


@dataclass(frozen=True)
class Source:
    """Where one glyph's bytes are: a file a run configured, or a bundle member.

    Frozen because :func:`_read` caches on it.
    """

    name: str
    path: Path | None = None

    def read(self) -> bytes:
        if self.path is not None:
            return self.path.read_bytes()
        bundle = _bundle()
        if bundle is None:
            raise SpecError(f"the glyph bundle {BUNDLE} is gone")
        return bundle.read(self.name)

    def __str__(self) -> str:
        return str(self.path) if self.path is not None else f"{BUNDLE}:{self.name}"


@functools.lru_cache(maxsize=1)
def _bundle() -> zipfile.ZipFile | None:
    """The opened bundle, or None where it is absent or unreadable."""
    if not BUNDLE.is_file():
        return None
    try:
        return zipfile.ZipFile(BUNDLE)
    except (OSError, zipfile.BadZipFile):
        return None


def builtin_bytes(name: str) -> bytes | None:
    """The shipped SVG called ``name`` (no extension), or None."""
    bundle = _bundle()
    if bundle is None:
        return None
    try:
        return bundle.read(f"{name}.svg")
    except KeyError:
        return None


@dataclass(frozen=True)
class Glyph:
    """One icon's geometry, ready to become a shape."""

    name: str
    view: tuple[float, float, float, float]
    subpaths: tuple[str, ...]  # each an SVG 'd', in the view's own units

    def drawingml(self) -> str:
        """Every subpath as one ``a:path`` body, so an inner contour cuts a hole."""
        return to_drawingml([c for d in self.subpaths for c in parse(d)], view=self.view)


def configured(theme) -> tuple[Path, ...]:
    """The directories a run adds ahead of the shipped set: env, then the theme's own."""
    found: list[Path] = []
    declared = env_str(None, _ICON_DIR_ENV_VAR, default="")
    if declared:
        found.append(Path(declared))
    if theme is not None and theme.icons is not None:
        found.append(theme.icons)
    return tuple(found)


def roots(theme) -> tuple[Path, ...]:
    """Where an icon name is looked for, in order: env, the theme's own, ours."""
    return configured(theme) + (BUNDLE,)


def load(name: str, *, theme=None) -> Glyph:
    """The glyph called ``name``.

    A configured directory wins outright, so a brand can replace any name; aliases run
    last, so they can never shadow a glyph that already resolved.

    Raises:
        SpecError: the name is not a plain lowercase slug, or nothing holds it — the
            message names the closest real glyphs.
    """
    if not _NAME.match(name or ""):
        raise SpecError(
            f"icon name {name!r} must be lowercase letters, digits, hyphens and "
            f"underscores — it names a file, not a label"
        )
    found = (
        _in(name, configured(theme))
        or _find(OVERRIDES.get(name, ""), theme)
        or _find(name, theme)
        or _find(ALIASES.get(name, ""), theme)
    )
    if found is None:
        raise SpecError(_unknown(name, theme))
    return _read(found, name)


def supplied(name: str, theme=None) -> Path | None:
    """The file a *configured* directory holds for ``name``, or None.

    Asked before a preset is drawn, so a brand shipping its own ``diamond.svg`` wins.
    """
    found = _in(name, configured(theme))
    return found.path if found is not None else None


def _in(name: str, dirs: tuple[Path, ...]) -> Source | None:
    """The file holding ``name`` in ``dirs``, or None."""
    for root in dirs:
        candidate = root / f"{name}.svg"
        if candidate.is_file():
            return Source(name=f"{name}.svg", path=candidate)
    return None


def _builtin(name: str) -> Source | None:
    """The bundle's member for ``name``, or None."""
    bundle = _bundle()
    if bundle is None or not name:
        return None
    member = f"{name}.svg"
    try:
        bundle.getinfo(member)
    except KeyError:
        return None
    return Source(name=member)


def _find(name: str, theme) -> Source | None:
    """Where ``name`` resolves, or None. Hyphens fall back to the vendored spelling."""
    if not name:
        return None
    return _in(name, configured(theme)) or _builtin(name) or _builtin(name.replace("-", "_"))


@functools.lru_cache(maxsize=1)
def available() -> tuple[str, ...]:
    """Every name the shipped set carries, sorted. Cached: it is thousands of names."""
    bundle = _bundle()
    if bundle is None:
        return ()
    return tuple(sorted(n.removesuffix(".svg") for n in bundle.namelist() if n.endswith(".svg")))


def search(term: str) -> tuple[str, ...]:
    """Every glyph name containing ``term``, sorted, with its aliases.

    An alias is returned under the name an author would write, not the vendored one
    it resolves to, so searching "globe" finds the word that works in a deck.
    """
    needle = term.strip().lower().replace("-", "_")
    names = set(available())
    hits = {n for n in names if needle in n}
    hits |= {n for n in (*ALIASES, *OVERRIDES) if needle in n.replace("-", "_")}
    return tuple(sorted(hits))


def _unknown(name: str, theme) -> str:
    """The miss message: what was searched, and what is close."""
    if _bundle() is None:
        return (
            f"no icon {name!r}: the built-in glyph bundle is missing from {BUNDLE} "
            f"— run 'bin/setup', or 'deckwright glyphs sync' to rebuild it"
        )
    vocabulary = set(available()) | set(ALIASES) | set(OVERRIDES)
    near = difflib.get_close_matches(name.replace("-", "_"), vocabulary, n=_SUGGESTIONS, cutoff=0.7)
    lead = (
        f"Did you mean {', '.join(near)}?"
        if near
        else f"Nothing close among the {len(vocabulary):,} names available."
    )
    return f"no icon {name!r} in {', '.join(str(r) for r in roots(theme))}. {lead}"


@functools.lru_cache(maxsize=256)
def _read(source: Source, name: str) -> Glyph:
    """Parse one SVG. Cached on the source, since a deck reuses an icon many times."""
    try:
        root = parse_xml(source.read())
    except (OSError, KeyError, etree.XMLSyntaxError) as e:
        raise SpecError(f"icon {name!r} at {source} is not readable SVG: {e}") from e
    box = (root.get("viewBox") or "").split()
    if len(box) != 4:
        raise SpecError(
            f"icon {name!r} has no usable viewBox — deckwright scales by it, so an icon "
            f"without one has no size to scale from"
        )
    subpaths = tuple(str(el.get("d")) for el in root.iter(f"{_SVG}path") if el.get("d"))
    if not subpaths:
        raise SpecError(
            f"icon {name!r} holds no <path> — strokes, circles and rects are not read; "
            f"flatten the drawing to paths"
        )
    vx, vy, vw, vh = (float(v) for v in box)
    return Glyph(name=name, view=(vx, vy, vw, vh), subpaths=subpaths)
