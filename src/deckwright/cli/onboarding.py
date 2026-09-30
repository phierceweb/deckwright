"""Onboarding commands: scaffold a deck, demo the library, or adopt a brand template."""

from __future__ import annotations

import shlex
from pathlib import Path

import typer

from deckwright.cli._app import app
from deckwright.compile.build import theme_dir
from deckwright.compile.scaffold import new_deck
from deckwright.conform import conform as run_conform
from deckwright.conform.demo import demo as run_demo
from deckwright.errors import SpecError


@app.command()
def new(
    name: str = typer.Argument(..., help="The deck's name — spaced or hyphenated."),
    theme: str = typer.Option("base", "--theme", "-t", help="Theme the deck names."),
    root: Path = typer.Option(
        Path("authoring"), "--root", help="Where the deck's source directory goes."
    ),
    build: bool = typer.Option(True, "--build/--no-build", help="Compile it straight away."),
) -> None:
    """Start a deck: write one that already builds, then build it."""
    made = new_deck(name, root=root, theme=theme, build=build)
    typer.echo(f"spec    -> {made.spec}")
    if made.built is not None:
        deck = made.built.deck.resolve()
        typer.echo(f"deck    -> {deck}")
        typer.echo(f"words   -> {deck.with_suffix('.content.md')}")
    typer.echo(f"edit the spec, then: deckwright build {made.spec}")


@app.command()
def demo(
    theme: str = typer.Option(
        "base", "--theme", "-t", help="Theme name, resolved against the theme directory."
    ),
    outdir: Path = typer.Option(Path("out/demo"), "--out", "-o", help="Where to write the deck."),
) -> None:
    """Build every capability the library has into one deck, against any theme."""
    deck = run_demo(theme, outdir)
    typer.echo(f"deck    -> {deck}")
    typer.echo(f"words   -> {deck.with_suffix('.content.md')}")


@app.command()
def conform(
    template: Path = typer.Argument(..., help="A brand .pptx to drive."),
    outdir: Path = typer.Option(
        Path("out/conform"), "--out", "-o", help="Where to write the derived theme and deck."
    ),
    adopt: str | None = typer.Option(
        None,
        "--adopt",
        metavar="NAME",
        help="Keep the derived theme as "
        "<theme dir>/NAME.theme.yaml, beside the "
        "template it binds to — that file, not the "
        "one under out/, is the one to read and edit.",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="With --adopt, re-derive over an existing theme "
        "of that name. Its edits are not recoverable.",
    ),
) -> None:
    """Exercise every capability against a brand template and report what it carries."""
    result = run_conform(template, outdir / template.stem[:40], adopt=adopt, force=force)
    typer.echo(result.report())
    if result.theme:
        typer.echo(f"theme -> {result.theme}")
    if result.deck:
        typer.echo(f"deck  -> {result.deck}")
    if result.adopted:
        typer.echo(f"adopted -> {result.adopted}  (edit this one; out/ is disposable)")
    if not result.ok:
        raise typer.Exit(1)


@app.command()
def sample(
    path: Path = typer.Argument(
        None, help="Where to write it. Defaults to <theme dir>/sample.pptx."
    ),
    force: bool = typer.Option(False, "--force", help="Overwrite an existing file at that path."),
) -> None:
    """Write a small brand template to conform against, so onboarding needs no brand file."""
    from deckwright.conform.sample import write_sample

    root = theme_dir()
    # Default into the theme dir: --adopt refuses a template anywhere else.
    if path is None:
        path = root / "sample.pptx"
    if path.exists() and not force:
        raise SpecError(f"{path} already exists — pass --force to replace it")
    written = write_sample(path)
    typer.echo(f"sample  -> {written}")
    if written.resolve().parent == root.resolve():
        typer.echo(f"try it: deckwright conform {shlex.quote(str(written))} --adopt sample")
    else:
        typer.echo(
            f"to adopt it: mkdir -p {shlex.quote(str(root))} && mv {shlex.quote(str(written))} "
            f"{shlex.quote(str(root))}/ && "
            f"deckwright conform {shlex.quote(str(root / written.name))} --adopt sample"
        )


@app.command()
def doctor() -> None:
    """Report what this install can do: glyphs, themes, and the external tools."""
    from deckwright.doctor import main as run_doctor

    raise typer.Exit(run_doctor())
