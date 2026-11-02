"""Every chart module must import cleanly in a fresh interpreter — a plain pytest run
cannot see a cycle here, because ``conftest`` resolves ``deckwright.layouts`` first."""

from __future__ import annotations

import subprocess
import sys

import pytest

_CHART_MODULES = ("deckwright.charts.model", "deckwright.charts.native")


@pytest.mark.parametrize("module", _CHART_MODULES)
def test_a_chart_module_imports_cleanly_in_a_fresh_process(module: str) -> None:
    result = subprocess.run(
        [sys.executable, "-c", f"import {module}"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
