"""deckwright command-line entry point.

Wired through pf-core's CLI scaffold, so ``--verbose`` logging and
exception-to-exit-code mapping work out of the box.
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

import typer

from pf_core.cli import create_cli, run_cli
from pf_core.log import setup_logging
from pf_core.utils.io import atomic_write_text

from deckwright.conform import conform as run_conform
from deckwright.compile.readback import read_back, write_drift
from deckwright.compile.scaffold import new_deck
from deckwright.conform.demo import demo as run_demo

from deckwright.compile import build_deck
from deckwright.compile.build import theme_dir
from deckwright.config import load_env
from deckwright.paths import render_dir
from deckwright.errors import MissingToolError, SpecError
from deckwright.compile.record import box_of
from deckwright.qa import Severity, inspect_deck, run_qa
from deckwright.services.htmlshot import render_html_to_png
from deckwright.services.montage import contact_sheet as build_contact_sheet
from deckwright.services.render import render_to_images
from deckwright.spec.draft import draft_spec
from deckwright.spec.extract import harvest, render_markdown

# An unexpected exception gets a plain traceback: typer's pretty one adds a locals panel,
# which here means slide markup and rendered HTML on the terminal.
app = create_cli(
    "deckwright",
    help="deckwright — build and render PowerPoint decks.",
    pretty_exceptions_enable=False,
)


def _print_version(show: bool) -> None:
    if show:
        from deckwright.doctor import installed_version

        typer.echo(f"deckwright {installed_version()}")
        raise typer.Exit()


@app.callback()
def _root(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logging"),
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        callback=_print_version,
        is_eager=True,
        help="Print the installed version and exit.",
    ),
) -> None:
    # Registering a callback for --version replaces pf-core's, so its logging wiring
    # is redone here rather than reached for through Typer's registry.
    setup_logging(level="DEBUG" if verbose else None)


@app.command()
def build(
    spec: Path = typer.Argument(..., help="Path to the .deck.yaml to compile."),
    theme: Path | None = typer.Option(
        None,
        "--theme",
        "-t",
        help="Theme file (default: the spec's 'theme:' name, resolved against the theme dir, then the packaged built-ins).",
    ),
    out: Path | None = typer.Option(
        None, "--out", "-o", help="Output .pptx (overrides the spec's 'out:')."
    ),
    keep_layouts: bool = typer.Option(
        False,
        "--keep-layouts",
        help="Keep the template's unused slide layouts and masters, and the media only they reach.",
    ),
) -> None:
    """Compile a deck spec into a .pptx and its build manifest."""
    result = build_deck(spec, theme_path=theme, out=out, keep_layouts=keep_layouts)
    typer.echo(f"built {result.slides} slide(s) -> {result.deck}")
    typer.echo(f"manifest -> {result.manifest}")


@app.command()
def render(
    pptx: Path = typer.Argument(..., help="Path to the .pptx to render."),
    outdir: Path | None = typer.Option(
        None, "--outdir", "-o", help="Output dir (default: <pptx-dir>/render/<deck>)."
    ),
    dpi: int | None = typer.Option(
        None, "--dpi", help="Rasterization DPI (default 110 / $DECKWRIGHT_RENDER_DPI)."
    ),
    contact_sheet: bool = typer.Option(
        False, "--contact-sheet", help="Also write a contact-sheet overview PNG."
    ),
    cols: int = typer.Option(4, "--cols", help="Columns in the contact sheet."),
) -> None:
    """Render each slide of a deck to an image (LibreOffice + pdftoppm)."""
    out = outdir or render_dir(pptx)
    images = render_to_images(pptx, out, dpi=dpi)
    typer.echo(f"rendered {len(images)} slide(s) -> {out}")
    if contact_sheet:
        sheet = build_contact_sheet(images, out / "contact_sheet.png", cols=cols)
        typer.echo(f"contact sheet -> {sheet}")


@app.command()
def shot(
    html: Path = typer.Argument(..., help="Path to an .html file to screenshot."),
    out: Path | None = typer.Option(
        None, "--out", "-o", help="Output .png (default: alongside the .html)."
    ),
    width: int = typer.Option(1000, "--width", "-w", help="Layout width in CSS px."),
    scale: int | None = typer.Option(
        None, "--scale", help="Device scale factor ($DECKWRIGHT_SHOT_SCALE, default 2)."
    ),
) -> None:
    """Screenshot an HTML file to a PNG (headless Chrome, cropped to content)."""
    dest = out or html.with_suffix(".png")
    render_html_to_png(html.read_text(encoding="utf-8"), dest, width=width, scale=scale)
    typer.echo(f"wrote {dest}")


@app.command()
def qa(
    deck: Path = typer.Argument(..., help="Path to the built .pptx."),
    manifest: Path | None = typer.Option(
        None, "--manifest", "-m", help="Build manifest (default: <deck>.manifest.json)."
    ),
    theme: Path | None = typer.Option(
        None, "--theme", "-t", help="Theme file (default: the one recorded in the manifest)."
    ),
    no_render: bool = typer.Option(
        False, "--no-render", help="Skip the render-based overflow and contrast checks."
    ),
    fail_on: str | None = typer.Option(
        None, "--fail-on", help="Exit non-zero at this severity or worse: error|warn|info."
    ),
    outdir: Path | None = typer.Option(
        None,
        "--outdir",
        "-o",
        help="Where to write qa.md / qa.json (default: <deck-dir>/render/<deck>).",
    ),
) -> None:
    """Check a built deck for geometry, typography and overflow problems."""
    threshold: Severity | None = None
    if fail_on is not None:
        try:
            threshold = Severity(fail_on)
        except ValueError:
            raise SpecError(
                f"--fail-on must be one of {', '.join(s.value for s in Severity)}, got {fail_on!r}"
            ) from None

    try:
        report = run_qa(
            deck, manifest=manifest, theme_path=theme, render=not no_render, outdir=outdir
        )
    except MissingToolError as e:
        raise MissingToolError(
            f"{e}\nOr re-run with --no-render for the checks that need no external "
            "tool: bounds, placement, reserved regions, type sizes and contrast."
        ) from e
    if not report.findings:
        typer.echo("no findings")
    else:
        for finding in report.findings:
            typer.echo(
                f"slide {finding.slide}: [{finding.severity.value}] "
                f"{finding.check} — {finding.detail}"
            )
        typer.echo(f"{len(report.findings)} finding(s)")
    if threshold is not None and report.exceeds(threshold):
        raise typer.Exit(1)


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
    force: bool = typer.Option(False, "--force", help="Overwrite an existing file at that path."),
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
    if fmt == "md":
        text = render_markdown(slides, title=deck.stem)
    else:
        drafted = draft_spec(slides, title=deck.stem, theme=theme, source=deck.name)
        text, spilled = drafted.text, drafted.spilled
    dest.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(dest, text)
    typer.echo(f"{len(slides)} slide(s) -> {dest}")
    lost = sum(len(slide.dropped) for slide in slides)
    if lost:
        typer.echo(f"{lost} shape(s) could not be converted — each is named in {dest.name}")
    if spilled:
        typer.echo(f"{spilled} line(s) reached no placement — each is named in {dest.name}")


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
    # Default into the theme dir: --adopt refuses a template anywhere else, so writing
    # beside the caller printed a next step that always exited 1.
    if path is None:
        path = root / "sample.pptx"
    if path.exists() and not force:
        raise SpecError(f"{path} already exists — pass --force to replace it")
    written = write_sample(path)
    typer.echo(f"sample  -> {written}")
    if written.resolve().parent == root.resolve():
        typer.echo(f"try it: deckwright conform {written} --adopt sample")
    else:
        typer.echo(
            f"to adopt it: mkdir -p {root} && mv {written} {root}/ && "
            f"deckwright conform {root / written.name} --adopt sample"
        )


@app.command()
def doctor() -> None:
    """Report what this install can do: glyphs, themes, and the external tools."""
    from deckwright.doctor import main as run_doctor

    raise typer.Exit(run_doctor())


glyphs_app = typer.Typer(help="The built-in Material Symbols set: check it, re-vendor it.")
app.add_typer(glyphs_app, name="glyphs")


@glyphs_app.command("find")
def glyphs_find(
    term: str = typer.Argument(..., help="Substring to look for. Hyphens and underscores match."),
    limit: int = typer.Option(40, "--limit", help="Most names to print. 0 prints all."),
) -> None:
    """Search the glyph names for one to put in an `icon:`."""
    from deckwright.icons.load import available, search

    hits = search(term)
    if not hits:
        typer.echo(f"no glyph name contains {term!r} — {len(available()):,} names available")
        raise typer.Exit(1)
    shown = hits if limit <= 0 else hits[:limit]
    for name in shown:
        typer.echo(name)
    if len(shown) < len(hits):
        typer.echo(f"... {len(hits) - len(shown):,} more — narrow the term, or --limit 0")


@glyphs_app.command("verify")
def glyphs_verify() -> None:
    """Check the shipped glyph bundle against its manifest."""
    from deckwright.icons import vendor

    problems = vendor.verify()
    for problem in problems:
        typer.echo(problem)
    if problems:
        raise typer.Exit(1)
    ref, hashes = vendor.read_manifest()
    typer.echo(f"{len(hashes):,} glyphs, matching {vendor.MANIFEST.name} @ {ref[:12]}")


@glyphs_app.command("sync")
def glyphs_sync(
    ref: str | None = typer.Option(
        None,
        "--ref",
        metavar="COMMIT",
        help="Upstream commit to vendor. Omit to rebuild the set the manifest already pins.",
    ),
) -> None:
    """Fetch the upstream icons and rewrite the bundle and its manifest.

    Needs a network, and the fetch is large. With no --ref this reproduces the
    pinned set; with one it adopts a newer upstream, and `git diff` on the manifest is
    the review surface.
    """
    from deckwright.icons import vendor

    if not vendor.MATERIAL.parent.is_dir():
        raise SpecError("glyphs can only be synced from a source checkout")
    changed = vendor.sync(ref)
    typer.echo(
        f"vendored {changed['kept']:,} glyphs @ {str(changed['ref'])[:12]} "
        f"({changed['dropped']} dropped — they need nonzero winding)"
    )
    for label in ("added", "removed", "changed"):
        names = changed[label]
        if names:
            shown = ", ".join(names[:8]) + (" …" if len(names) > 8 else "")
            typer.echo(f"  {label:<8} {len(names):>4}  {shown}")
    if not any(changed[k] for k in ("added", "removed", "changed")):
        typer.echo("  the set is unchanged")


def main() -> None:
    # Findings quote deck copy, which carries em dashes and curly quotes whatever the
    # console encoding is. Without this a legacy code page raises instead of printing.
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(errors="replace")
    load_env()
    run_cli(app)


if __name__ == "__main__":
    main()
