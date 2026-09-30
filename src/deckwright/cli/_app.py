"""The shared Typer app and root callback every CLI command module registers against."""

from __future__ import annotations

import typer

from pf_core.cli import create_cli
from pf_core.log import setup_logging

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
