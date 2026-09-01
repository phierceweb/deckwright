"""The gate that refuses hand-rolled framework code has to keep refusing it. Its failure mode is
silent — a regex that stops matching, an exemption that widens — so each rule is exercised against
source that breaks it, and against source that only mentions it."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "bin" / "check-framework"
pytestmark = pytest.mark.skipif(
    not GATE.exists(), reason="no bin/ — running from an sdist, which ships only the package"
)

BREACHES = [
    ("import logging\n", "logging"),
    ("def f():\n    raise RuntimeError('x')\n", "RuntimeError"),
    ("def f():\n    raise ValueError('x')\n", "ValueError"),
    ("def f():\n    raise Exception('x')\n", "Exception"),
    ("import os\n\n\ndef f():\n    return os.environ.get('X')\n", "environ"),
    ("def f():\n    print('x')\n", "print"),
    (
        "import logging\n\nlogger = logging.getLogger(__name__)\n\n\n"
        "def f():\n    logger.exception('x')\n",
        "logger.exception",
    ),
    ("import os\n\n\ndef f(a, b):\n    os.replace(a, b)\n", "os.replace"),
    ("import concurrent.futures\n", "concurrent.futures"),
]


def _run(*paths: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(GATE), *(str(p) for p in paths)],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )


@pytest.mark.parametrize("source,needle", BREACHES, ids=[n for _, n in BREACHES])
def test_the_gate_refuses_each_hand_roll(source, needle, tmp_path):
    breach = tmp_path / "breach.py"
    breach.write_text(source)
    result = _run(breach)
    assert result.returncode == 1, f"{needle} passed the gate:\n{result.stdout}"
    assert "use" in result.stdout, "a failure that does not name the replacement teaches nothing"


def test_the_gate_does_not_fire_on_prose_that_merely_names_a_rule():
    """A doc mentioning ``os.environ`` documents the rule; it does not break it. `config.py`'s own
    docstring says "reads ``os.environ`` at call time", and it must stay green."""
    assert _run(ROOT / "src/deckwright/config.py").returncode == 0


def test_the_package_passes_its_own_gate():
    """The gate is worth nothing if the tree it guards is already red — a red gate is one
    people learn to skip."""
    result = _run()
    assert result.returncode == 0, result.stdout


def _gate_module():
    import importlib.util

    spec = importlib.util.spec_from_loader(
        "check_framework", importlib.machinery.SourceFileLoader("check_framework", str(GATE))
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_every_exemption_states_a_reason():
    """An exemption is a claim someone can check. A blank one is a blanket skip wearing
    a key, and that is how a gate rots into decoration."""
    module = _gate_module()

    assert module.EXEMPT, "no exemptions at all is suspicious — the file shape changed"
    for key, reason in module.EXEMPT.items():
        assert len(key) == 2, f"an exemption must name (rule, filename): {key}"
        assert len(reason.split()) >= 4, f"{key} is exempt for no stated reason: {reason!r}"


def test_every_exemption_names_the_file_and_the_rule_it_covers():
    """The reason-length check above cannot see *what* an exemption is for. The gate's table is the
    whole record, so the reason has to say what the file does that earns the exemption."""
    for (rule, filename), reason in _gate_module().EXEMPT.items():
        # The stem, not the path: "panels/cache.py" is explained by talking about the
        # cache, and a reason is prose rather than a path listing.
        stem = Path(filename).stem.lower()
        said = reason.lower()
        assert stem in said or rule.replace("-", " ") in said or rule in said, (
            f"exemption ({rule}, {filename}) explains itself without naming either the "
            f"rule or the file it covers: {reason!r}"
        )
