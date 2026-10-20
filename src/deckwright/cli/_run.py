"""Turn what a command raises into a message on stderr and an exit code."""

from __future__ import annotations

import sys

import typer
from rich.console import Console
from rich.markup import escape
from typer._click.exceptions import ClickException

from pw_foundation.exceptions import AppError, FlowException
from pw_foundation.log import log_exception

_stderr = Console(stderr=True)


def _print_error(exc: BaseException) -> None:
    # Escaped because a message is data: rich drops a bare `[x, y]` and raises on `[/]`.
    _stderr.print(f"[red]{escape(str(exc))}[/red]")


def run_cli(app: typer.Typer, *, args: list[str] | None = None) -> None:
    """Run ``app`` and exit the way a shell script calling deckwright expects.

    - ``typer.Exit(N)`` exits N, and Ctrl-C exits 130 (typer raises it as ``Exit(130)``).
    - A usage error (an unknown option, a missing argument, a bad choice) prints typer's
      usage message and exits with its code, 2.
    - ``FlowException`` — a malformed spec or theme, a missing tool — prints its message
      and exits 1.
    - ``AppError`` — a renderer that ran and failed — is logged with its traceback, then
      prints its message and exits 1.

    Args:
        app: The Typer application to run.
        args: The command line; ``sys.argv`` when omitted.
    """
    try:
        code = app(standalone_mode=False, args=args)
    except ClickException as exc:
        exc.show()
        sys.exit(exc.exit_code)
    except FlowException as exc:
        _print_error(exc)
        sys.exit(1)
    except AppError as exc:
        log_exception(exc, message_prepend="cli error")
        _print_error(exc)
        sys.exit(1)
    # Outside standalone mode typer returns an Exit's code instead of raising it.
    if isinstance(code, int) and code != 0:
        sys.exit(code)
