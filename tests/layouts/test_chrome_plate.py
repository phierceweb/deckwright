"""Where a chrome line's last-resort plate goes, and what it may cover."""

from __future__ import annotations

import json

from deckwright.compile import build_deck

# The sky deck's noon slide: a white Sun placed right of a short subtitle, inside the
# subtitle's full-measure band but nowhere under its words.
_SPEC = """\
theme: base
title: T
out: out/P.pptx
---
background: inverse
kicker: PART 2 · SUNSETS
title: At noon, sunlight takes a short path through the air
subtitle: Straight down through the layer. Call this one unit of air.
place:
  - at: {box: {x: 60.5%, y: 24%, w: 8%, h: 14.22%}}
    ellipse: {pair: page, label: Sun}
"""


def _shapes(tmp_path):
    spec = tmp_path / "p.deck.yaml"
    spec.write_text(_SPEC)
    built = build_deck(spec)
    return json.loads(built.manifest.read_text())["slides"][0]["shapes"]


def test_a_shape_beside_a_chrome_lines_words_gets_no_plate(tmp_path):
    """Probed across its whole measure, the subtitle met the Sun it never crosses and
    painted a full-width bar of slide paper over the disc's top."""
    assert [s["name"] for s in _shapes(tmp_path) if s.get("plate")] == []


def test_a_plate_is_named_for_its_line_and_reaches_up_to_where_the_words_can_rise(tmp_path):
    """The title's two-line estimate set on one line in the render, lifting the subtitle a
    line above the slot its plate was painted in."""
    spec = tmp_path / "p.deck.yaml"
    spec.write_text(
        _SPEC.split("place:")[0]
        + "place:\n  - at: {box: {x: 0%, y: 13%, w: 40%, h: 4%}}\n"
        + "    bleed: true\n    panel: {pair: page}\n"
    )
    shapes = json.loads(build_deck(spec).manifest.read_text())["slides"][0]["shapes"]
    plates = {s["name"]: s["box"] for s in shapes if s.get("plate")}
    assert "s1.chrome.subtitle.plate" in plates
    # The subtitle's estimated slot starts at 1.725in; one title line higher is 1.16in.
    assert plates["s1.chrome.subtitle.plate"]["y"] < 1.16
