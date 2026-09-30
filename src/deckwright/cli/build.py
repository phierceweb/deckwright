"""Build, render and QA commands: compile a deck, rasterize it, screenshot HTML, check it."""

from __future__ import annotations

from pathlib import Path

import typer

from deckwright.cli._app import app
from deckwright.compile import build_deck
from deckwright.errors import MissingToolError, SpecError
from deckwright.paths import render_dir
from deckwright.qa import Severity, run_qa
from deckwright.services.htmlshot import render_html_to_png
from deckwright.services.montage import contact_sheet as build_contact_sheet
from deckwright.services.render import render_to_images


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
