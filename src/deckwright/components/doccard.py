"""Render a real markdown file as a slide graphic, so it cannot drift from the source."""

from __future__ import annotations

from pathlib import Path

from deckwright.errors import LayoutError
from deckwright.layouts.components import BodyResult, component
from deckwright.layouts.registry import SlideCtx
from deckwright.panels.css import panel_css
from deckwright.panels.model import Panel
from deckwright.panels.place import place_panel
from deckwright.services.htmlcard import markdown_card

from deckwright.components._shape import figure_text, known_fields
from deckwright.components._shared import coerce_int, require_default_align

_MAX_WIDTH_DEFAULT = 1000
_SIDES = ("left", "right", "full")


def _render(html: str, path: str, *, width: int, scale: int) -> str:
    from deckwright.services.htmlshot import render_html_to_png

    return render_html_to_png(html, path, width=width, scale=scale)


_FIELDS = ("source", "alt", "decorative", "side", "max_width", "filename", "lines")


def _excerpt(ctx: SlideCtx, text: str, spec: object, path: Path) -> str:
    """``lines: 12-40`` — one-based and inclusive, the way an editor names them."""
    raw = str(spec).strip()
    start_text, _, end_text = raw.partition("-")
    try:
        start, end = int(start_text), int(end_text)
    except ValueError:
        raise LayoutError(
            f"slide {ctx.spec.index} (component 'document'): 'lines' must look like "
            f"'12-40' — one-based and inclusive, got {raw!r}"
        ) from None
    if start < 1 or end < start:
        raise LayoutError(
            f"slide {ctx.spec.index} (component 'document'): 'lines' must start at 1 or "
            f"more and end at or after its start, got {raw!r}"
        )
    available = text.splitlines()
    if start > len(available):
        raise LayoutError(
            f"slide {ctx.spec.index} (component 'document'): 'lines' starts at {start} "
            f"but {path} has only {len(available)} line(s) — the excerpt is gone from "
            f"the source, so the card would be empty"
        )
    return "\n".join(available[start - 1 : end])


def _resolve_source(ctx: SlideCtx, source: str) -> Path:
    """Beside the deck spec, then as given — the rule every other path in a spec follows."""
    given = Path(source)
    if given.is_absolute():
        return given
    for root in ctx.media_roots:
        beside = root / given
        if beside.exists():
            return beside
    return given


@component("document")
def document(ctx: SlideCtx) -> BodyResult:
    """Place ``source`` markdown as a rendered window card (see :func:`_resolve_source`)."""
    require_default_align(ctx)
    known_fields(ctx, _FIELDS)
    alt, decorative = figure_text(ctx)
    source = ctx.body.get("source")
    if not source:
        raise LayoutError(f"slide {ctx.spec.index} (component 'document'): 'source' is required")
    path = _resolve_source(ctx, str(source))
    if not path.exists():
        raise LayoutError(
            f"slide {ctx.spec.index} (component 'document'): source not found: "
            f"{source} — looked beside the deck spec and in {Path.cwd()}"
        )
    if not path.is_file():
        raise LayoutError(
            f"slide {ctx.spec.index} (component 'document'): source is not a file: {path}"
        )

    side = str(ctx.body.get("side", "full"))
    if side not in _SIDES:
        raise LayoutError(
            f"slide {ctx.spec.index} (component 'document'): 'side' must be one of "
            f"{', '.join(_SIDES)}, got {side!r}"
        )

    max_width = coerce_int(ctx, "max_width", ctx.body.get("max_width"), _MAX_WIDTH_DEFAULT)
    if max_width <= 0:
        raise LayoutError(
            f"slide {ctx.spec.index} (component 'document'): 'max_width' must be positive, "
            f"got {max_width}"
        )
    try:
        md_text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as e:
        raise LayoutError(
            f"slide {ctx.spec.index} (component 'document'): {path} is not valid UTF-8 text"
        ) from e
    if "lines" in ctx.body:
        md_text = _excerpt(ctx, md_text, ctx.body["lines"], path)
    html = markdown_card(
        md_text,
        filename=str(ctx.body.get("filename", path.name)),
        max_width=max_width,
        content_css=panel_css(ctx.theme),
    )

    rect = ctx.body_rect
    width = rect.width if side == "full" else (rect.width - ctx.grid.gutter) / 2
    left = rect.left if side in ("full", "left") else rect.left + width + ctx.grid.gutter

    placed = place_panel(
        ctx,
        Panel(html=html, width=max_width),
        left=left,
        top=rect.top,
        width=width,
        render=_render,
        alt=alt,
        decorative=decorative,
    )
    picture = placed[""]
    height = picture.height / 914400
    if height > rect.height:
        raise LayoutError(
            f"slide {ctx.spec.index} (component 'document'): the card came out {height:.2f}in "
            f"tall but only {rect.height:.2f}in is available — card fewer lines with "
            f"'lines: 12-40', raise 'max_width' to set the type smaller, or use "
            f"'side: left'/'side: right' to narrow it. Do not copy part of the file "
            f"into a shorter one; the copy is what this component exists to avoid"
        )
    return BodyResult(groups=[[(picture.shape_id, "figure")]], height=height)
