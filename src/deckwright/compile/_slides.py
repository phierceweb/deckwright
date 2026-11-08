"""Which slide of its build each deck slide is, for ``diff``: the deck's slides aligned to the
build's, why a slide answers to none, and which slides are out of build order.
"""

from __future__ import annotations

from deckwright.compile._drift import Change
from deckwright.spec.matching import Drawn, morphs, numbers, same, tally


def moved_slides(placed: list[tuple[int, int]], *, built: int) -> list[Change]:
    """The slides out of build order, as few as explain the order the deck is in.

    ``placed`` is ``(build number, position)`` in deck order. The longest run still in build
    order stayed put; the rest were moved.
    """
    order = [index for index, _ in placed]
    best: list[list[int]] = []
    for i, number in enumerate(order):
        runs = [best[j] for j in range(i) if order[j] < number]
        longest: list[int] = []
        for run in runs:
            if len(run) > len(longest):
                longest = run
        best.append([*longest, number])
    stayed: set[int] = set()
    for run in best:
        if len(run) > len(stayed):
            stayed = set(run)
    return [
        Change("slide-moved", index, f"slide {index}", f"built at {index} of {built}, now at {at}")
        for index, at in placed
        if index not in stayed
    ]


# Compared in order: an exact match, how alike an edited slide is, how many of its shapes are
# the build slide's, whether its first-drawn shape is, how much of its transition and notes it keeps.
_Score = tuple[int, int, int, int, int]
_NOTHING: _Score = (0, 0, 0, 0, 0)
_Pairs = dict[tuple[int, int], _Score]
_NAMED = 5  # the likeness of a slide carrying the same morph names


def paired(
    deck: list[Drawn],
    built: dict[int, Drawn | None],
    *,
    kinds: list[str],
    built_kinds: dict[int, str | None],
    notes: list[str],
    built_notes: dict[int, str],
    firsts: list[int | None],
) -> dict[int, int]:
    """Each deck slide's position and the build slide it answers to, by the rules
    ``docs/compile.md`` gives under Read-back.

    The slides are aligned in order, keeping the most matched; a slide matched exactly only out
    of order then takes what is left, before a slide paired only by likeness; and a slide still
    unmatched takes a free build slide between its matched neighbours by likeness. ``kinds`` and
    ``notes`` are what each deck slide arrives on and carries, ``firsts`` the slide number of the
    first build-named shape it draws; ``built_kinds`` and ``built_notes`` are the same for each
    build slide.
    """
    order = sorted(built)
    exact: _Pairs = {}
    alike: _Pairs = {}
    retimed: _Pairs = {}
    for p, shapes in enumerate(deck, start=1):
        for i in order:
            record = built[i] or {}
            arrives = built_kinds.get(i)
            noted = built_notes.get(i, "") == notes[p - 1]
            kept = int(arrives == kinds[p - 1]) + int(noted)
            carried = _carried(shapes, record, i, arrives in (None, kinds[p - 1]), noted)
            if carried is not None:
                exact[(p, i)] = (1, 0, carried, int(firsts[p - 1] == i), kept)
                continue
            if (ours := morphs(shapes)) and same(ours, morphs(record)):
                retimed[(p, i)] = (1, 0, 0, 0, kept)
            if likeness := _likeness(shapes, record, noted):
                alike[(p, i)] = (0, likeness, 0, 0, kept)
    edited = {p for p in range(1, len(deck) + 1) if not any((p, i) in exact for i in order)}
    out = _aligned(
        list(range(1, len(deck) + 1)),
        order,
        {**{pair: s for pair, s in alike.items() if pair[0] in edited}, **exact},
    )
    _take_back(out, exact)
    _take_back(out, {pair: s for pair, s in retimed.items() if pair[1] not in out.values()})
    unmatched_slides = [p for p in range(1, len(deck) + 1) if p not in out]
    for (low, high), group in _between(unmatched_slides, out, max(order, default=0) + 1).items():
        taken = set(out.values())
        free = [i for i in order if low < i < high and i not in taken]
        likely = {
            (p, i): s
            for (p, i), s in alike.items()
            if p in group and (p in edited or s[1] >= _NAMED or not (deck[p - 1] or built[i]))
        }
        out.update(_aligned(group, free, likely))
    return out


def _aligned(positions: list[int], indices: list[int], scores: _Pairs) -> dict[int, int]:
    """The order-preserving pairing of ``positions`` with ``indices`` whose scores sum highest;
    of equals, the one taking the lowest build slides."""
    n, m = len(positions), len(indices)
    best = [[_NOTHING] * (m + 1) for _ in range(n + 1)]
    for a in range(n - 1, -1, -1):
        for b in range(m - 1, -1, -1):
            options = [best[a + 1][b], best[a][b + 1]]
            if found := scores.get((positions[a], indices[b])):
                options.append(_plus(found, best[a + 1][b + 1]))
            best[a][b] = max(options)
    out: dict[int, int] = {}
    a = b = 0
    while a < n and b < m:
        found = scores.get((positions[a], indices[b]))
        if found and _plus(found, best[a + 1][b + 1]) == best[a][b]:
            out[positions[a]] = indices[b]
            a, b = a + 1, b + 1
        elif best[a + 1][b] == best[a][b]:
            a += 1
        else:
            b += 1
    return out


def _take_back(out: dict[int, int], exact: _Pairs) -> None:
    """Pair each slide matched exactly only out of order, best evidence first, with a build slide
    that is free or held only by likeness; the slide it displaces is left unmatched."""
    held = {i: p for p, i in out.items()}
    for (p, i), _ in sorted(exact.items(), key=lambda pair: (pair[1], -pair[0][1]), reverse=True):
        if p in out or (i in held and (held[i], i) in exact):
            continue
        if i in held:
            del out[held[i]]
        out[p] = i
        held[i] = p


def _between(
    positions: list[int], out: dict[int, int], past: int
) -> dict[tuple[int, int], list[int]]:
    """``positions``, in deck order, grouped by the build numbers of the matched slides either
    side of them: 0 before the first and ``past`` after the last."""
    groups: dict[tuple[int, int], list[int]] = {}
    matched = sorted(out)
    for p in sorted(positions):
        before = [out[q] for q in matched if q < p][-1:]
        after = [out[q] for q in matched if q > p][:1]
        key = (before[0] if before else 0, after[0] if after else past)
        groups.setdefault(key, []).append(p)
    return groups


def _carried(
    shapes: Drawn, record: Drawn, index: int, agrees: bool, notes_agree: bool
) -> int | None:
    """How many of deck slide ``shapes`` are build slide ``index``'s — named for it, or its morph
    shapes drawn exactly as built, where ``agrees`` says the slide arrives on the build slide's
    transition; None when nothing matches exactly. Two empty slides match on the same transition
    and notes."""
    ours = morphs(shapes)
    drawn = bool(ours) and agrees and same(ours, morphs(record))
    named = tally(shapes)[index]
    if named or drawn:
        return named + (len(ours) if drawn else 0)
    if not shapes and not record and agrees and notes_agree:
        return 0
    return None


def _likeness(shapes: Drawn, record: Drawn, noted: bool) -> int:
    """How alike an edited slide is to a build slide: the same morph names in the same places,
    the same names, one name shared; or two empty slides, then a slide emptied or holding only
    shapes added by hand where the build left one empty, either nearer for the same notes."""
    ours, theirs = morphs(shapes), morphs(record)
    if ours and theirs and ours.keys() == theirs.keys():
        return _NAMED + 1 if same(ours, theirs, words=False) else _NAMED
    if ours.keys() & theirs.keys():
        return 2
    if not shapes and not record:
        return 2 + 2 * noted
    if not shapes or (not record and not ours):
        return 1 + 2 * noted
    return 0


def _plus(a: _Score, b: _Score) -> _Score:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2], a[3] + b[3], a[4] + b[4])


def unmatched(shapes: Drawn, matched: dict[int, int], built: dict[int, Drawn | None]) -> str:
    """Why a deck slide answers to no slide of the build."""
    found = sorted(numbers(shapes))
    if len(found) > 1:
        return f"holds shapes named for slides {_listed(found)}, so it answers to none of them"
    if found and found[0] in matched.values():
        return f"a copy of slide {found[0]} — added by hand"
    if not found and morphs(shapes):
        twin = next(
            (
                i
                for i in sorted(matched.values())
                if same(morphs(shapes), morphs(built.get(i) or {}))
            ),
            None,
        )
        if twin is not None:
            return f"a copy of slide {twin} — added by hand"
        return (
            "its morph shapes match no slide of the build — added by hand, or moved and edited both"
        )
    return "not in the build — added by hand"


def _listed(found: list[int]) -> str:
    *head, last = found
    return f"{', '.join(str(n) for n in head)} and {last}"
