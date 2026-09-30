"""The `glyphs` sub-app: search, verify and re-vendor the built-in Material Symbols set."""

from __future__ import annotations

import typer

from deckwright.cli._app import app
from deckwright.errors import SpecError

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
