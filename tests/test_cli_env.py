"""The CLI must load .env, or every DECKWRIGHT_* knob is inert unless shell-exported."""

from __future__ import annotations

import os
import subprocess
import sys

# A theme name with no packaged builtin, so resolution fails and the error
# names the directory it searched — which is what these tests read back.
SPEC = "theme: brand\nout: out.pptx\n---\ntitle: T\n"


def _run(cwd) -> subprocess.CompletedProcess:
    env = {**os.environ, "COLUMNS": "300"}
    env.pop("DECKWRIGHT_THEME_DIR", None)
    return subprocess.run(
        [sys.executable, "-m", "deckwright.cli", "build", "d.deck.yaml"],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
    )


def test_a_knob_set_in_dotenv_reaches_the_build(tmp_path):
    (tmp_path / ".env").write_text("DECKWRIGHT_THEME_DIR=/nope-themes\n")
    (tmp_path / "d.deck.yaml").write_text(SPEC)
    result = _run(tmp_path)
    assert result.returncode != 0
    assert "/nope-themes/brand.theme.yaml" in result.stdout + result.stderr


def test_without_a_dotenv_the_default_theme_dir_is_used(tmp_path):
    (tmp_path / "d.deck.yaml").write_text(SPEC)
    result = _run(tmp_path)
    assert result.returncode != 0
    assert "templates/brand.theme.yaml" in result.stdout + result.stderr
