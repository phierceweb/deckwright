"""The shared Typer app and root callback every CLI command module registers against."""

from __future__ import annotations

import typer

from pw_foundation.log import setup_logging

# An unexpected exception gets a plain traceback: typer's pretty one adds a locals panel,
# which here means slide markup and rendered HTML on the terminal.
app = typer.Typer(
    name="deckwright",
    help="deckwright — build and render PowerPoint decks.",
    add_completion=False,
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
    setup_logging(level="DEBUG" if verbose else None)
