# Lessons — what each click is for

A deck presented live spends clicks, and each click should change what the room knows. This
page names the moves a teaching deck makes and the spec for each, so a build is chosen for
what it teaches rather than reached for because a list has items.

Not the wire format — that is [`authoring.md`](authoring.md#animate). Not which shape a slide
earns — that is [`treatments.md`](treatments.md). This page is the third choice per slide:
what a click does.

## Table of Contents

- [The moves](#the-moves)
- [Choosing between them](#choosing-between-them)
- [Clicks cost time](#clicks-cost-time)
- [What a render cannot show](#what-a-render-cannot-show)

## The moves

| Move | When | Spec | Clicks |
|---|---|---|---|
| **Predict, then see** | The room can commit to a guess before it is told | A question as the title, the evidence on the slide; the claim as the next slide's title, the evidence carried by `transition: morph` and `carry: previous` — or repeated, for a chart, which takes no `morph:` | none on the slide; the advance is the reveal |
| **Step through** | The order is the lesson: a process, a derivation, a chain of causes | `animate: one_at_a_time` on a `flow` or `callouts` | one per step |
| **Build the picture** | Each layer earns a sentence of its own | A morph sequence: one slide per layer, each titled with what the new layer adds, `carry: previous` so each names only the new shape | none; one slide per layer |
| **Change the picture** | The same objects move, grow or recolour to show a consequence | A morph pair: the same `morph:` names in new places or pairs | none; the advance |
| **Hold two in view** | A comparison read whole | No build: `versus`, a mirrored pair, two placements side by side | none |
| **Fill in a scaffold** | A worked example: the structure first, then what goes in it | The structure `animate: none`, each entry a placement after it, `animate: one_at_a_time` | one per entry |
| **Hold the answer back** | Recall: the room answers before the slide does | Question and answer placements in that order under `one_at_a_time`; `reveals:` instead when presenting with a mouse or handing the deck out | one per answer |
| **Bars, then the claim** | A chart's categories are the argument and the room should see them land | `animate: by_category` and the claim in a placement after the chart | one per category, one for the axes, one for the claim |

**A list whose order is not the lesson needs no build.** Five reasons that are all true at
once arrive together, or with `together` after the title; a click per reason teaches the room
to wait, not to think.

## Choosing between them

Ask what the room does on the click. If the answer is *reads the next item*, the build is
pacing the deck and `together` is cheaper. If it is *checks a guess*, *sees the next step
follow from the last*, or *watches the picture change*, the click is teaching — and the moves
that change the picture (build, change, predict) are the ones a contact sheet can show beat
by beat, because each beat is a slide of its own.

Vary the move with the content. Three slides in a row ending on the same move are a rhythm
the room learns; [`treatments.md`](treatments.md#the-run-test) gives the levers, and `qa`'s
`rhythm` counts the run.

## Clicks cost time

A click is a pause the presenter has to fill. Count them before presenting: every build writes
`<deck>.beats.md` beside the deck, listing what arrives on each click in words, and `qa`'s
`beats` line gives each slide's total. A chart building by category spends one click on its
empty axes before the first bar.

## What a render cannot show

`bin/run render` draws every slide in its final state, so a build is invisible to it and to
the contact sheet. `.beats.md` is how to read a build without PowerPoint. A morph sequence is
the exception: each of its beats is a whole slide, so the contact sheet shows the lesson as
the room will see it.

**Bars, then the claim** has not been played in PowerPoint, nor has a title line with
`build: last`. Both validate against the schema; neither has been seen to run, and
[`motion.md`](motion.md#verification) lists what has. Rehearse them in the room's software before the talk,
or use the predict-then-see pair, whose motion is a slide change.
