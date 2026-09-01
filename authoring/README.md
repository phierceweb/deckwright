# Decks you are writing

Your `.deck.yaml` sources and anything they read — markdown for a `document:`, images,
a theme variant only this deck uses. One directory per deck.

Start one with `bin/run new "<Name>"` — it writes a working six-slide deck here and
builds it, so you edit something that runs instead of composing from nothing.

**Everything here except this README is gitignored.** A deck written for an audience is
your content, not the library's; it has no business in deckwright's history. Nothing here
is ever committed, so nothing has to be kept out by hand.

```
authoring/
  service-layer-testability/
    service-layer-testability.deck.yaml
    facade-code.md
```

The directory is `authoring` rather than `decks` because a *deck* is the `.pptx` you
present. What you write here is the spec for one — [`docs/authoring.md`](../docs/authoring.md)
says how, and the built deck lands in [`out/`](../out/README.md).

## Building one

`out:` resolves against the spec file, so point it into `out/` under a directory of its
own — `render` and `qa` both write beside the `.pptx`, and two decks sharing a directory
overwrite each other's slides.

```yaml
theme: base
out: ../../out/my-deck/My Deck v1.pptx
```

```bash
bin/run build authoring/my-deck/my-deck.deck.yaml
bin/run render "out/my-deck/My Deck v1.pptx" --contact-sheet
bin/run qa "out/my-deck/My Deck v1.pptx"
```

Then **look at the images**. QA checks what it can measure; it cannot tell you the deck
is unconvincing. Never overwrite a deck you have sent someone — bump `v1` to `v2`.

## Where to start

| You have | Read |
|---|---|
| A story and some data, no idea what to draw | [`docs/choosing.md`](../docs/choosing.md) |
| A process, steps, or anything with arrows | [`docs/flows.md`](../docs/flows.md) |
| A shape in mind, and you need the syntax | [`docs/authoring.md`](../docs/authoring.md) |
| A component to place | [`docs/components.md`](../docs/components.md) |
| An error message | [`docs/errors.md`](../docs/errors.md) |
| A brand template nobody has onboarded | [`docs/conform.md`](../docs/conform.md) |

You do not have to work here. A spec can live anywhere — `bin/run build
~/work/pitch.deck.yaml` is fine. This is the documented place *inside* the repo where a
deck cannot be committed by accident.
