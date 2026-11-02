"""The run test, counted from the manifest: what the eye sees repeat, not component names."""

from __future__ import annotations

from typing import Any

from deckwright.compile.record import box_of, owns
from deckwright.qa.model import Finding, Severity
from deckwright.qa.walk import slides
from deckwright.theme.model import Theme

_PLATE = frozenset({"card", "flow", "code", "panel", "stats", "versus", "fanout", "diverge"})
_TYPE = frozenset({"bullets", "callouts", "prose", "equation"})
_FIGURE = frozenset({"chart", "image", "document"})
_MARK = frozenset({"rule", "connector", "icon", "ellipse", "nav"})
_BAND = frozenset({"callouts", "bullets", "stats"})
# Five or more marks placed by hand are a drawn figure, not furniture.
_DRAWN = 5
_LOOK_RUN = 4
_BUILD_RUN = 4
_FOOTERS = 3
_TITLE_TOP_MIN = 8


def check_rhythm(manifest: dict[str, Any], theme: Theme) -> list[Finding]:
    """INFO findings for the runs `treatments.md`'s run test asks an author to count: a look
    repeated slide after slide, a band closing slide after slide, a title that never moves,
    and a build that reveals one group per click slide after slide."""
    canvas = manifest.get("canvas") or {}
    w, h = (
        float(canvas.get("w") or theme.grid.slide_w),
        float(canvas.get("h") or theme.grid.slide_h),
    )
    looks = [(s["index"], _look(s, w, h), s.get("transition") == "morph") for s in slides(manifest)]
    findings = [_run(looks)] if looks else []
    footed = [s["index"] for s in slides(manifest) if _footed(s, w, h)]
    if len(footed) >= _FOOTERS and len(footed) * 4 >= len(looks):
        findings.append(
            _info(
                footed[0],
                f"{len(footed)} slides end on a band under the body ({_list(footed)}) — a "
                f"composition of its own, whatever sits above it; treatments.md counts it",
            )
        )
    content = [look for _, look, _ in looks if look[1] != "field"]
    if len(content) >= _TITLE_TOP_MIN and all(look[2] == "top" for look in content):
        findings.append(
            _info(
                looks[0][0],
                f"the title sits at the top on all {len(content)} slides with a body — "
                f"chrome is the one element that never varies unless it is moved",
            )
        )
    findings.append(_builds(manifest))
    return [f for f in findings if f is not None]


def _look(slide: dict[str, Any], w: float, h: float) -> tuple[str, str, str]:
    """A slide's ground, its mass, and where its title sits."""
    area: dict[str, float] = {}
    marks = 0
    shapes = slide.get("shapes") or []
    for placement in slide.get("placements") or []:
        component, origin = str(placement.get("component")), str(placement.get("origin"))
        if component in _MARK:
            marks += 1
            continue
        # What the placement drew, not the rectangle it was given: a list hugs its rows.
        drawn = {
            box for s in shapes if owns(origin, str(s.get("name") or "")) and (box := box_of(s))
        }
        mass = (
            "plates"
            if component in _PLATE
            else "type"
            if component in _TYPE
            else "a figure"
            if component in _FIGURE
            else "a table"
            if component == "table"
            else component
        )
        area[mass] = area.get(mass, 0.0) + sum(b[2] * b[3] for b in drawn)
    mass = "a figure" if marks >= _DRAWN else max(area, key=area.__getitem__, default="field")
    title = next(
        (
            box_of(s)
            for s in slide.get("shapes") or []
            if str(s.get("name", "")).endswith(".chrome.title")
        ),
        None,
    )
    where = "none"
    if title is not None:
        x, y, tw, _ = title
        where = "side" if tw < 0.45 * w else "low" if y > 0.4 * h else "top"
    return str(slide.get("background") or "page"), mass, where


def _run(looks: list[tuple[int, tuple[str, str, str], bool]]) -> Finding | None:
    best: tuple[int, int] = (0, 0)
    start = 0
    for i in range(1, len(looks) + 1):
        if i == len(looks) or looks[i][1] != looks[start][1]:
            if i - start > best[1] - best[0]:
                best = (start, i)
            start = i
    first, end = best
    if end - first < _LOOK_RUN:
        return None
    ground, mass, title = looks[first][1]
    morphed = sum(1 for _, _, by_morph in looks[first:end] if by_morph)
    tail = f", {morphed} arriving by morph" if morphed else ""
    return _info(
        looks[first][0],
        f"slides {looks[first][0]}–{looks[end - 1][0]}: {end - first} in a row on {ground}, "
        f"{mass}, the title {'at the ' if title in ('top', 'side') else ''}{title}{tail} — "
        f"the run test reads them as one treatment",
    )


def _footed(slide: dict[str, Any], w: float, h: float) -> bool:
    """Whether the slide's lowest placement is a band of rows under a body above it."""
    placed = [
        (box, str(p.get("component")))
        for p in slide.get("placements") or []
        if (box := box_of(p)) is not None and p.get("component") not in _MARK
    ]
    if len(placed) < 2:
        return False
    (x, y, bw, bh), component = max(placed, key=lambda item: item[0][1])
    return component in _BAND and y > 0.6 * h and bw > 0.6 * w


def _builds(manifest: dict[str, Any]) -> Finding | None:
    """The longest run of slides that each build one group per click."""
    best: list[int] = []
    run: list[int] = []
    for slide in slides(manifest):
        kinds = [a.get("kind") for a in slide.get("animations") or []]
        if kinds == ["click_sequence"] and int(slide["animations"][0].get("clicks", 0)) > 1:
            run.append(slide["index"])
            best = max(best, run, key=len)
        else:
            run = []
    if len(best) < _BUILD_RUN:
        return None
    return _info(
        best[0],
        f"slides {best[0]}–{best[-1]}: {len(best)} in a row reveal one group per click — when "
        f"the click stops changing what the room learns, the build is pacing the deck",
    )


def _list(indices: list[int]) -> str:
    return ", ".join(str(i) for i in indices)


def _info(slide: int, detail: str) -> Finding:
    return Finding(slide=slide, check="rhythm", severity=Severity.INFO, detail=detail)
