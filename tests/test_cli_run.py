"""What `deckwright.cli._run.run_cli` does with an exception no other CLI test raises."""

from __future__ import annotations

import pytest

import deckwright.cli._run as runner
import deckwright.cli.build as build_cli
from deckwright.cli import app
from deckwright.errors import RenderError, SpecError


def _raising(exc):
    def build_deck(*args, **kwargs):
        raise exc

    return build_deck


def test_a_message_reaches_stderr_as_written_and_alone(monkeypatch, capsys):
    """A spec quotes the author's YAML back, and rich reads `[left, right]` as a style and `[/]`
    as a closing tag — dropping the one and raising inside the handler on the other. Alone: a bad
    spec is the author's to fix, so it gets no log line beside it."""
    message = "slide 3: at: [left, right] is not a placement; [/] is not a fraction"
    monkeypatch.setattr(build_cli, "build_deck", _raising(SpecError(message)))

    with pytest.raises(SystemExit) as stop:
        runner.run_cli(app, args=["build", "d.deck.yaml"])

    assert stop.value.code == 1
    assert " ".join(capsys.readouterr().err.split()) == message


def test_a_usage_error_prints_the_usage_line_and_exits_2(capsys):
    with pytest.raises(SystemExit) as stop:
        runner.run_cli(app, args=["build", "--nope"])

    assert stop.value.code == 2
    err = capsys.readouterr().err
    assert "Usage:" in err
    assert "No such option: --nope" in err


def test_a_renderer_failure_is_logged_then_exits_1(monkeypatch, capsys):
    """An AppError is a bug or a broken tool, so its traceback goes to the log as well."""
    failure = RenderError("soffice exited 134")
    logged = []
    monkeypatch.setattr(build_cli, "build_deck", _raising(failure))
    monkeypatch.setattr(runner, "log_exception", lambda exc, **kw: logged.append(exc))

    with pytest.raises(SystemExit) as stop:
        runner.run_cli(app, args=["build", "d.deck.yaml"])

    assert stop.value.code == 1
    assert logged == [failure]
    assert "soffice exited 134" in capsys.readouterr().err
