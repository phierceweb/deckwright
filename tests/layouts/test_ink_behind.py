"""Text a component sets on the slide is inked for what is painted behind it, not for the
slide's nominal background, and the manifest records that ground.

The `_CASES` run on a slide whose whole canvas carries a dark panel. With the fixture palette
(ink 2D0937, page FFFFFF, accent-1 27B94C) the only inks that read there are the page colour
and the bright accent, and nothing sits on the white page at all. The `_PAINTERS` are the
components whose own fills later text can sit on.
"""

from __future__ import annotations

import pytest

import deckwright.components  # noqa: F401 — registers the built-ins
from deckwright.layouts.components import get_component
from deckwright.layouts.registry import Disc
from deckwright.theme.model import Rect

_DARK = "12161B"
_READS_ON_DARK = {"FFFFFF", "27B94C"}

_CASES = {
    "prose": {"paragraphs": ["Copy set over a dark panel."], "cite": "Someone"},
    "bullets": {"heading": "Why", "items": ["One", "Two"]},
    "callouts": {"heading": "Notes", "items": [{"head": "A head", "body": "A body line"}]},
    "stats": {"items": [{"value": "12", "label": "units"}], "caption": "A caption"},
    "nav": {"items": ["Problem", "Evidence"], "active": "Evidence"},
    "fanout": {"source": "publish(post)", "items": [{"text": "Digest"}, {"text": "Cache"}]},
    "diverge": {"items": [{"label": "North", "value": 3, "note": "a note"}]},
    "code": {"heading": "Listing", "lines": ["print('hi')"]},
    "table": {"header": ["A", "B"], "rows": [["one", "two"]]},
    "grid": {},
}


def _on_dark(ctx_factory, component, body):
    ctx = ctx_factory({component: body})
    ctx.painted.append((Rect(0.0, 0.0, 13.333, 7.5), _DARK))
    ctx.manifest.origin = f"s1.p1.{component}"
    get_component(component)(ctx)
    return [s for s in ctx.manifest.slides[0].shapes if s.fg and s.bg]


@pytest.mark.parametrize("component", list(_CASES))
def test_no_text_record_claims_the_page_under_a_panel_that_covers_it(ctx_factory, component):
    records = _on_dark(ctx_factory, component, _CASES[component])
    assert records, "the case drew no text record, so it checks nothing"
    assert [r.name for r in records if r.bg == "FFFFFF"] == []


@pytest.mark.parametrize("component", list(_CASES))
def test_text_on_a_dark_panel_is_inked_to_read_on_it(ctx_factory, component):
    records = [r for r in _on_dark(ctx_factory, component, _CASES[component]) if r.bg == _DARK]
    assert records, "no record sits on the panel, so the ink is unchecked"
    assert {r.name: r.fg for r in records if r.fg not in _READS_ON_DARK} == {}


_PAINTERS = {
    "panel": {"pair": "inverse"},
    "card": {"pair": "inverse", "heading": "A plate"},
    "ellipse": {"pair": "inverse"},
    "callouts": {"items": [{"head": "A head", "body": "A body line"}]},
    "versus": {
        "left": {"value": "3", "label": "before"},
        "right": {"value": "9", "label": "after"},
    },
    "diverge": {"pair": "inverse", "items": [{"label": "North", "value": 3}]},
    "fanout": {"source": "publish(post)", "items": [{"text": "Digest"}, {"text": "Cache"}]},
    "grid": {},
}


@pytest.mark.parametrize("component", list(_PAINTERS))
def test_a_fill_a_component_paints_is_what_text_laid_over_it_is_on(ctx_factory, component):
    """A later placement's text over a `bleed:` fill is inked for the fill, not the page."""
    ctx = ctx_factory({component: _PAINTERS[component]})
    ctx.manifest.origin = f"s1.p1.{component}"
    get_component(component)(ctx)
    filled = next(s for s in ctx.slide.shapes if s.fill.type == 1)  # MSO_FILL.SOLID
    box = Rect(*(v / 914400 for v in (filled.left, filled.top, filled.width, filled.height)))
    centre = Rect(box.left + box.width * 0.45, box.top + box.height * 0.45, 0.01, 0.01)
    assert str(filled.fill.fore_color.rgb) != "FFFFFF", (
        "the fill is the page, so this proves nothing"
    )
    assert ctx.behind(centre, ink="FFFFFF") == str(filled.fill.fore_color.rgb)


def test_prose_over_a_dark_disc_is_inked_to_read_on_it(ctx_factory):
    ctx = ctx_factory({"ellipse": {"pair": "inverse"}})
    ctx.manifest.origin = "s1.p1.ellipse"
    get_component("ellipse")(ctx)
    disc = ctx.slide.shapes[0]
    d = disc.width / 914400
    ctx.component, ctx.body = "prose", {"paragraphs": ["On the disc."]}
    ctx.rect = Rect(disc.left / 914400 + d * 0.3, disc.top / 914400 + d * 0.4, d * 0.4, d * 0.2)
    ctx.manifest.origin = "s1.p2.prose"
    get_component("prose")(ctx)
    [prose] = [s for s in ctx.manifest.slides[0].shapes if s.lines or s.text]
    assert (prose.fg, prose.bg) == ("FFFFFF", str(disc.fill.fore_color.rgb))


def test_the_corner_of_a_discs_frame_shows_what_is_under_the_disc(ctx_factory):
    """A disc covers its inscribed square; its frame's corner is still the page."""
    ctx = ctx_factory({})
    frame = Rect(1.0, 1.0, 4.0, 4.0)
    ctx.painted.append((frame, Disc(_DARK)))
    assert ctx.behind(Rect(1.05, 1.05, 0.2, 0.2), ink="FFFFFF") == "FFFFFF"
    assert ctx.behind(Rect(2.9, 2.9, 0.2, 0.2), ink="FFFFFF") == _DARK


def test_the_drawn_runs_carry_the_ink_the_record_names(ctx_factory):
    """A record is only a claim: the run's colour in the file is what is on screen."""
    ctx = ctx_factory({"prose": {"paragraphs": ["Copy over dark."]}})
    ctx.painted.append((Rect(0.0, 0.0, 13.333, 7.5), _DARK))
    get_component("prose")(ctx)
    run = ctx.slide.shapes[0].text_frame.paragraphs[0].runs[0]
    assert str(run.font.color.rgb) == "FFFFFF"


def test_muted_text_off_the_page_takes_the_surfaces_own_ink(ctx_factory):
    """The muted role is vetted against the page only; on a surface it may read and still
    be the wrong voice, so a caption there takes surface-ink (2D0937), not muted (573C65)."""
    ctx = ctx_factory(
        {"stats": {"items": [{"value": "12", "label": "units"}], "caption": "A caption"}},
        background="surface",
    )
    ctx.manifest.origin = "s1.p1.stats"
    get_component("stats")(ctx)
    [caption] = [s for s in ctx.manifest.slides[0].shapes if s.text == "A caption"]
    assert caption.fg == "2D0937"
