"""``diff``'s slide pairing against generated decks and scripted hand edits, whose truth is known
by construction.

A reading the deck holds no evidence to decide is accepted either way (`_wrong` names each);
every other slide must be read as the build slide it is, or as `slide_oracle_known.json` says.
"""

from __future__ import annotations

import copy
import json
import random
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from pptx import Presentation
from pptx.oxml.ns import qn

from deckwright.compile import build_deck
from deckwright.compile.readback import read_back
from deckwright.utils.deck import delete_slide

_TIMING = (
    qn("p:transition"),
    "{http://schemas.openxmlformats.org/markup-compatibility/2006}AlternateContent",
)
_SEEDS = range(1, 41)
# Each generated edit `diff` reads wrong, with the reading it gives: an undecided case the oracle's
# model does not cover, or a misreading `docs/cli.md` lists under `diff`.
_KNOWN: dict[str, list[str]] = json.loads(
    Path(__file__).with_name("slide_oracle_known.json").read_text(encoding="utf-8")
)


@dataclass
class _Truth:
    build: int | None  # the build slide this deck slide is; None for one added by hand
    copy_of: int | None = None  # on a duplicate: the build slide it copies
    edits: set[str] = field(default_factory=set)


def _held(x: int, transition: str | None) -> str:
    lead = f"transition: {transition}\n" if transition else ""
    return (
        f"{lead}place:\n  - at: {{box: {{x: {x}%, y: 20%, w: 30%, h: 30%}}}}\n"
        "    morph: fig\n    card: {heading: Held, body: words}\n"
    )


def _spec(rng: random.Random, n: int) -> tuple[str, list[str]]:
    slides, kinds = [], []
    for i in range(n):
        roll = rng.random()
        if roll < 0.45:
            slides.append(f"title: Slide {i + 1}\n")
            kinds.append("titled")
        elif roll < 0.85:
            slides.append(_held(rng.choice([0, 20, 40, 60]), rng.choice([None, "morph", "none"])))
            kinds.append("morph")
        else:
            transition = rng.choice([None, "morph", "none"])
            notes = rng.choice([None, "alpha", "beta"])
            body = (f"transition: {transition}\n" if transition else "") + (
                f"notes: {notes}\n" if notes else ""
            )
            slides.append(body or "notes: plain\n")
            kinds.append("empty")
    return "theme: base\nout: out/G.pptx\n---\n" + "---\n".join(slides), kinds


def _retime(prs, target: int, source: int) -> None:
    element = prs.slides[target]._element
    for child in [c for c in element if c.tag in _TIMING]:
        element.remove(child)
    after = element.find(qn("p:clrMapOvr"))
    at = list(element).index(after) + 1 if after is not None else len(element)
    for k, child in enumerate([c for c in prs.slides[source]._element if c.tag in _TIMING]):
        element.insert(at + k, copy.deepcopy(child))


def _move(prs, source: int, target: int) -> None:
    ids = prs.slides._sldIdLst
    moved = ids[source]
    ids.remove(moved)
    ids.insert(target, moved)


def _edit(rng: random.Random, prs, truth: list[_Truth], state: dict[str, bool]) -> str:
    """Apply one hand edit to ``prs`` and keep ``truth`` in step with it."""
    n = len(truth)
    choice = rng.choice(
        ["delete", "move", "duplicate", "retype", "retime", "paste", "blank", "notes"]
    )
    i = rng.randrange(n)
    if choice in ("duplicate", "blank") and state.get("deleted"):
        return "none"  # python-pptx reuses a deleted slide's part name for the next one added
    if choice == "delete" and n > 2:
        delete_slide(prs, i)
        truth.pop(i)
        state["deleted"] = True
        return f"delete {i + 1}"
    if choice == "move":
        j = rng.randrange(n)
        _move(prs, i, j)
        truth.insert(j, truth.pop(i))
        truth[j].edits.add("moved")
        return f"move {i + 1}->{j + 1}"
    if choice == "duplicate":
        source = prs.slides[i]
        clone = prs.slides.add_slide(source.slide_layout)
        for shape in list(clone.shapes):
            shape._element.getparent().remove(shape._element)
        for shape in source.shapes:
            clone.shapes._spTree.append(copy.deepcopy(shape._element))
        _retime(prs, len(prs.slides) - 1, i)
        _move(prs, len(prs.slides) - 1, i + 1)
        original = truth[i].build if truth[i].build is not None else truth[i].copy_of
        truth.insert(i + 1, _Truth(None, copy_of=original))
        return f"duplicate {i + 1}"
    if choice == "retype":
        cards = [s for s in prs.slides[i].shapes if s.name == "m.fig.card#2"]
        if not cards:
            return "none"
        cards[0].text_frame.paragraphs[0].runs[0].text = "Changed"
        truth[i].edits.add("retyped")
        return f"retype {i + 1}"
    if choice == "retime":
        j = rng.randrange(n)
        _retime(prs, i, j)
        truth[i].edits.add("retimed")
        return f"retime {i + 1} like {j + 1}"
    if choice == "paste":
        j = rng.randrange(n)
        named = [s for s in prs.slides[i].shapes if s.name.startswith("s")]
        if not named or i == j:
            return "none"
        prs.slides[j].shapes._spTree.append(copy.deepcopy(named[0]._element))
        truth[j].edits.add("pasted")
        return f"paste {named[0].name} onto {j + 1}"
    if choice == "blank":
        added = prs.slides.add_slide(prs.slides[0].slide_layout)
        for shape in list(added.shapes):
            shape._element.getparent().remove(shape._element)
        k = rng.randrange(n + 1)
        _move(prs, len(prs.slides) - 1, k)
        truth.insert(k, _Truth(None, edits={"blank"}))
        return f"blank at {k + 1}"
    if choice == "notes":
        prs.slides[i].notes_slide.notes_text_frame.text = rng.choice(["", "alpha", "edited"])
        truth[i].edits.add("renoted")
        return f"notes {i + 1}"
    return "none"


def pairing(drift, slides: int, built: list[int]) -> dict[int, int]:
    """Each deck position and the build slide ``drift`` reads it as, from its added, gone and
    moved slides: the rest stayed in build order."""
    added = {c.slide for c in drift.of("slide-added")}
    gone = {c.slide for c in drift.of("slide-gone")}
    moved: dict[int, int] = {}
    for change in drift.of("slide-moved"):
        found = re.search(r"now at (\d+)$", change.detail)
        assert found, change.detail
        moved[int(found.group(1))] = change.slide
    positions = [p for p in range(1, slides + 1) if p not in added and p not in moved]
    indices = [i for i in built if i not in gone and i not in moved.values()]
    assert len(positions) == len(indices), (added, gone, moved)
    return {**dict(zip(positions, indices, strict=True)), **moved}


def _twins(data: dict[int, Any], a: int, b: int) -> bool:
    """Whether build slides ``a`` and ``b`` cannot be told apart: drawn, timed and noted alike."""

    def drawn(s: dict[str, Any]) -> list[tuple[Any, ...]]:
        return [(r.get("name"), json.dumps(r.get("box")), r.get("text")) for r in s["shapes"]]

    sa, sb = data[a], data[b]
    return (
        drawn(sa) == drawn(sb)
        and sa.get("transition") == sb.get("transition")
        and sa.get("notes") == sb.get("notes")
    )


def _blank_like(record: dict[str, Any]) -> bool:
    """A build slide a blank slide added by hand cannot be told from."""
    return not record["shapes"] and not record.get("notes") and record.get("transition") == "none"


def _wrong(
    truth: list[_Truth], got: dict[int, int], data: dict[int, Any], kinds: list[str]
) -> list[str]:
    """Every deck slide ``got`` reads as a build slide it is not, where the deck decides it."""
    present = {t.build for t in truth if t.build is not None}

    def is_(have: int | None, want: int) -> bool:
        return have is not None and (have == want or _twins(data, have, want))

    def kin(b: int) -> int:
        return min(i for i in data if _twins(data, i, b))

    wrong = []
    families: dict[int, list[int]] = {}
    copied = {kin(t.copy_of) for t in truth if t.copy_of is not None}
    for position, t in enumerate(truth, start=1):
        root = t.build if t.build is not None else t.copy_of
        if root is not None and kin(root) in copied:
            families.setdefault(kin(root), []).append(position)
    for root, positions in families.items():
        # A copy is drawn as its original and its twins: any of them may be read as one of
        # those, but every one still in the deck is read as one, and none as another slide.
        took = [got.get(q) for q in positions]
        held = sum(1 for b in present if kin(b) == root)
        if sum(h is not None for h in took) < held or any(
            h is not None and kin(h) != root for h in took
        ):
            wrong.append(f"build {root}, its twins and copies at {positions} read as {took}")
    in_family = {q for positions in families.values() for q in positions}
    for position, t in enumerate(truth, start=1):
        have = got.get(position)
        if position in in_family:
            continue
        if t.build is None:
            # A blank slide may be read as a build slide it cannot be told from, or one deleted.
            if have is not None and have in present and not _blank_like(data[have]):
                wrong.append(f"new slide at {position} took build {have}, still in the deck")
            continue
        if is_(have, t.build):
            continue
        if _undecided(position, have, truth, kinds, data, got):
            continue
        wrong.append(f"deck {position} is build {t.build}, read as {have}")
    return wrong


def _undecided(
    position: int,
    have: int | None,
    truth: list[_Truth],
    kinds: list[str],
    data: dict[int, Any],
    got: dict[int, int],
) -> bool:
    """Whether the edits left nothing that says which build slide deck slide ``position`` is, so
    reading it as ``have`` is as right as the truth."""
    t = truth[position - 1]
    assert t.build is not None
    kind = kinds[t.build - 1]
    if kind == "morph" and "retyped" in t.edits and have is None:
        before = [u.build for u in truth[: position - 1] if u.build is not None][-1:]
        after = [u.build for u in truth[position:] if u.build is not None][:1]
        # its drawing is no longer the build's, and its place is not either
        return bool(before and before[0] > t.build or after and after[0] < t.build)
    if kind == "empty" and t.edits & {"retimed", "renoted"}:
        # an empty slide is known only by its transition and notes: read as added, or as another
        # empty slide whose own deck slide lost those too
        if have is None:
            return True
        holder = next((u for u in truth if u.build == have), None)
        return kinds[have - 1] == "empty" and (
            holder is None or bool(holder.edits & {"retimed", "renoted"})
        )
    if have is None and _blank_like(data[t.build]):
        return any(u.build is None and got.get(q) == t.build for q, u in enumerate(truth, 1))
    return False


def run(seed: int, decks: int, per: int, work: Path) -> list[tuple[str, dict[int, int], list[str]]]:
    """``decks`` generated decks, ``per`` edited copies of each: every copy's edits, the
    pairing ``read_back`` gives it, and what that pairing gets wrong."""
    rng = random.Random(seed)
    work.mkdir(parents=True, exist_ok=True)
    results = []
    for d in range(decks):
        text, kinds = _spec(rng, rng.randrange(4, 9))
        (work / "g.deck.yaml").write_text(text)
        built = build_deck(work / "g.deck.yaml")
        data = {
            int(s["index"]): {**s, "shapes": list(s.get("shapes") or [])}
            for s in json.loads(Path(built.manifest).read_text())["slides"]
        }
        for e in range(per):
            prs = Presentation(str(built.deck))
            truth = [_Truth(i) for i in range(1, len(prs.slides) + 1)]
            state: dict[str, bool] = {}
            names = [_edit(rng, prs, truth, state) for _ in range(rng.choice([1, 1, 2]))]
            edited = work / f"e{d}_{e}.pptx"
            prs.save(str(edited))
            drift = read_back(edited, manifest=built.manifest)
            got = pairing(drift, len(truth), sorted(data))
            label = f"seed {seed} deck {d} copy {e} [{', '.join(names)}]"
            results.append((label, got, _wrong(truth, got, data, kinds)))
    return results


@pytest.mark.parametrize("seed", _SEEDS)
def test_diff_reads_each_generated_edit_as_the_slides_it_made(seed, tmp_path):
    known = {label: why for label, why in _KNOWN.items() if label.startswith(f"seed {seed} ")}
    read = {label: why for label, _, why in run(seed, 20, 6, tmp_path) if why or label in known}
    assert read == known
