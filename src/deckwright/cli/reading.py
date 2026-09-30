"""Read a built deck back: what changed, its shapes, or its words."""

from __future__ import annotations

import shutil
from pathlib import Path

import typer

from pf_core.utils.io import atomic_write_bytes, atomic_write_text

from deckwright.cli._app import app
from deckwright.compile.readback import read_back, write_drift
from deckwright.compile.record import box_of
from deckwright.errors import SpecError
from deckwright.qa import inspect_deck
from deckwright.spec.draft import draft_spec
from deckwright.spec.extract import harvest, render_markdown


@app.command()
def diff(
    deck: Path = typer.Argument(..., help="A built .pptx, hand-edited or not."),
    manifest: Path | None = typer.Option(
        None, "--manifest", "-m", help="Default: <deck>.manifest.json."
    ),
    outdir: Path | None = typer.Option(None, "--out", "-o", help="Also write readback.md here."),
) -> None:
    """Show what a hand-edited deck changed, so it can go back into the spec."""
    drift = read_back(deck, manifest=manifest)
    if not drift.edited:
        typer.echo(f"{deck.name} is the deck that was built — nothing to carry back.")
        return
    typer.echo(f"{deck.name} was edited after its build from {drift.spec}")
    for change in drift.changes:
        typer.echo(f"  slide {change.slide}  {change.kind:<8} {change.shape}  {change.detail}")
    if not drift.changes:
        typer.echo("  no shape differs — a resave, or a change this cannot see")
    if outdir is not None:
        typer.echo(f"report -> {write_drift(drift, outdir / 'readback.md')}")


@app.command()
def inspect(
    deck: Path = typer.Argument(..., help="Path to a .pptx to inventory."),
) -> None:
    """List every slide's shapes with ids, names and boxes — for surgical hand-edits."""
    slides = inspect_deck(deck)
    typer.echo(f"{deck.name}: {len(slides)} slide(s)")
    for slide in slides:
        typer.echo(f"slide {slide['index']} ({slide['layout']})")
        for shape in slide["shapes"]:
            found = box_of(shape)
            box = (
                f"{found[0]:.2f},{found[1]:.2f} {found[2]:.2f}×{found[3]:.2f}"
                if found
                else "no box"
            )
            typer.echo(f"  id={shape['shape_id']:<4} {box:<24} {shape['name']!r}")


@app.command()
def extract(
    deck: Path = typer.Argument(..., help="Path to a .pptx to read the words out of."),
    out: Path | None = typer.Option(
        None, "--out", "-o", help="Where to write (default: beside the deck)."
    ),
    fmt: str = typer.Option("yaml", "--as", help="yaml for a draft spec, md for a transcript."),
    theme: str = typer.Option("base", "--theme", "-t", help="Theme the draft names."),
    force: bool = typer.Option(
        False,
        "--force",
        help="Overwrite an existing file at that path, and replace the draft's media folder.",
    ),
) -> None:
    """Draft a .deck.yaml (or a transcript) from a deck deckwright did not build."""
    # Ordered, not incidental: nothing is read to reject a flag, and '.' and '/' have no
    # `with_name`, so the deck is checked before the default destination is derived.
    if fmt not in ("yaml", "md"):
        raise SpecError(f"--as must be 'yaml' or 'md', got {fmt!r}")
    if not deck.is_file():
        raise SpecError(f"deck {deck} is not a readable .pptx: no file at that path")
    dest = out or deck.with_name(deck.stem + (".md" if fmt == "md" else ".deck.yaml"))
    if dest.exists() and not force:
        raise SpecError(f"{dest} already exists — pass --force to replace it")
    slides = harvest(deck)
    spilled = 0
    media: dict[str, bytes] = {}
    folder = dest.parent / (dest.name.removesuffix(".deck.yaml").removesuffix(".yaml") + ".media")
    if fmt == "md":
        text = render_markdown(slides, title=deck.stem)
    else:
        drafted = draft_spec(
            slides, title=deck.stem, theme=theme, source=deck.name, media=folder.name
        )
        text, spilled, media = drafted.text, drafted.spilled, drafted.media
    if media and folder.exists(follow_symlinks=False):
        if not force:
            raise SpecError(f"{folder} already exists — pass --force to replace it")
        if folder.is_symlink() or not folder.is_dir():
            raise SpecError(
                f"{folder} is a file or a link, not a media folder — --force replaces a folder "
                f"and nothing else: move it aside, or pass another --out"
            )
    dest.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(dest, text)
    typer.echo(f"{len(slides)} slide(s) -> {dest}")
    if media:
        if folder.exists():
            shutil.rmtree(folder)
        for name, data in media.items():
            (dest.parent / name).parent.mkdir(parents=True, exist_ok=True)
            atomic_write_bytes(dest.parent / name, data)
        typer.echo(f"{len(media)} picture(s) -> {folder}")
    lost = sum(len(slide.dropped) for slide in slides)
    if lost:
        typer.echo(f"{lost} shape(s) could not be converted — each is named in {dest.name}")
    if spilled:
        typer.echo(f"{spilled} line(s) reached no placement — each is named in {dest.name}")
