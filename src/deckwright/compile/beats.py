"""Render a build manifest as the deck's reveal order.

Derived, never authoritative: regenerate it, do not edit it. ``.content.md`` is the same
build's words; this is when each of them arrives.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterator

from pf_core.utils.io import atomic_write_text

from deckwright.compile.content import split_name

# A beat line past this reads as a paragraph rather than a cue.
_WIDTH = 88

_KIND = {
    "click_build": "animate: together",
    "click_sequence": "animate: one_at_a_time",
    "click_reveals": "reveals:",
    "chart_build": "a chart's own build",
}


def render_beats(manifest: dict[str, Any]) -> str:
    """The deck's beats as markdown, slide by slide, in order."""
    deck = Path(str(manifest.get("deck") or "deck")).stem
    slides = manifest.get("slides") or []
    animated = [s for s in slides if s.get("animations")]
    clicks = sum(_clicks_of(a) for s in animated for a in s["animations"])
    triggers = sum(1 for s in animated for a in s["animations"] if a.get("kind") == "click_reveals")
    facts = [f"{len(animated)} of {len(slides)} slide(s) animate", f"{clicks} click(s)"]
    if triggers:
        facts.append(f"{triggers} interactive trigger(s)")
    if manifest.get("build_id"):
        facts.append(f"build `{manifest['build_id']}`")
    lines = [
        f"# Beats — {deck}",
        "",
        " · ".join(facts),
        "",
        "Derived from the build manifest. Regenerate it rather than edit it.",
        "",
    ]
    if not animated:
        lines += ["Nothing on this deck animates.", ""]
    for slide in animated:
        lines.extend(_slide(slide))
    return "\n".join(lines).rstrip() + "\n"


def write_beats(manifest: dict[str, Any], path: str | Path) -> Path:
    """Write the beats view beside the deck; returns the path."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, render_beats(manifest))
    return path


def _clicks_of(anim: dict[str, Any]) -> int:
    """The recorded click count, falling back to one click per beat where it is absent."""
    return int(anim.get("clicks", len(anim.get("steps") or [])))


def _said(shape: dict[str, Any]) -> str:
    lines = shape.get("lines") or ([shape["text"]] if shape.get("text") else [])
    return " — ".join(w for line in lines if (w := str(line).lstrip("•").strip()))


def _words(slide: dict[str, Any]) -> dict[str, str]:
    """What each shape says, keyed by its name and by the placement that drew it.

    A card's plate is drawn first and says nothing, so a trigger named by its shape would
    tell a reader nothing — hence the placement key.
    """
    out: dict[str, str] = {}
    for shape in reversed(slide.get("shapes") or []):
        name = str(shape.get("name") or "")
        said = _said(shape)
        out[name] = said
        if said:
            out[split_name(name)[0]] = said
    return out


def _slide(slide: dict[str, Any]) -> Iterator[str]:
    words = _words(slide)
    head = f"## Slide {slide.get('index')}"
    if title := words.get(f"s{slide.get('index')}.chrome.title"):
        head += f" · {title}"
    yield from ("---", "", head, "")
    reveals = [a for a in slide["animations"] if a.get("kind") == "click_reveals"]
    if reveals:
        yield f"`{_KIND['click_reveals']}` — no slide advance; each trigger fires on its own"
        yield ""
        for anim in reveals:
            trigger = str(anim.get("trigger") or "")
            named = words.get(trigger) or words.get(split_name(trigger)[0]) or trigger
            yield f"- click **{named}** → {_beat(anim['steps'][0], words)}"
        yield ""
    for anim in slide["animations"]:
        kind = str(anim.get("kind"))
        if kind == "click_reveals":
            continue
        clicks = _clicks_of(anim)
        yield f"`{_KIND.get(kind, kind)}` — {'1 click' if clicks == 1 else f'{clicks} clicks'}"
        yield ""
        if kind == "chart_build":
            yield "1. the chart's axes and gridlines"
            for i in range(2, clicks + 1):
                yield f"{i}. one of the chart's parts"
        else:
            for i, step in enumerate(anim["steps"], 1):
                yield f"{i}. {_beat(step, words)}"
        yield ""


def _beat(step: list[str], words: dict[str, str]) -> str:
    said = [w for w in (words.get(name) or "" for name in step) if w]
    if not said:
        return f"*({len(step)} shape(s), no words: {', '.join(step)})*"
    line = " · ".join(said)
    return line if len(line) <= _WIDTH else line[: _WIDTH - 1].rstrip() + "…"
