"""The gate that keeps imports pointing downward has to keep pointing them downward. Its failure
mode is not a crash: a RANK key that matches no module ranks nothing, and the gate goes on printing
"import-layering OK" over a tier it no longer separates."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "bin" / "check-layers"
pytestmark = pytest.mark.skipif(
    not GATE.exists(), reason="no bin/ — running from an sdist, which ships only the package"
)

UPWARD = [
    ("utils/deck.py", "deckwright.components"),
    ("theme/load.py", "deckwright.qa"),
    ("motion/builds.py", "deckwright.layouts"),
    ("services/render.py", "deckwright.conform"),
    ("errors.py", "deckwright.utils"),
    ("qa/inspect.py", "deckwright.cli"),
]


@pytest.fixture
def gate():
    """A fresh load of the gate — RANK, ROOT and SRC are module globals tests rewrite."""
    spec = importlib.util.spec_from_loader(
        "check_layers", importlib.machinery.SourceFileLoader("check_layers", str(GATE))
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def top_level(gate):
    """The package's top-level module names, read off disk rather than out of RANK."""
    return {p.name for p in gate.SRC.iterdir() if p.is_dir() and p.name != "__pycache__"} | {
        p.stem for p in gate.SRC.glob("*.py") if p.stem != "__init__"
    }


@pytest.fixture
def sandbox(gate, tmp_path, monkeypatch):
    """The package's .py files under a throwaway ROOT, with the gate pointed at them."""
    root = tmp_path / "tree"
    src = root / "src" / "deckwright"
    for path in gate.SRC.rglob("*.py"):
        target = src / path.relative_to(gate.SRC)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(path.read_bytes())
    monkeypatch.setattr(gate, "ROOT", root)
    monkeypatch.setattr(gate, "SRC", src)
    return src


def test_rank_names_no_module_that_moved_away(gate, top_level):
    """A key for a module that no longer exists ranks nothing and looks like it does — every import
    through it silently becomes unranked, which is when an inversion lands unseen."""
    stale = sorted(set(gate.RANK) - top_level)
    assert not stale, f"RANK ranks modules that are not on disk: {stale}"


def test_every_top_level_module_is_ranked(gate, top_level):
    """A package nobody placed in the tiering is a package nobody may be caught importing
    upward — the gate skips it in both directions."""
    assert not sorted(top_level - set(gate.RANK))


def test_the_gate_separates_more_than_two_layers(gate):
    """RANK's values are the tiers the gate can hold apart: a table down to two of them still exits
    0 on the whole tree while enforcing almost nothing."""
    ranks = sorted(set(gate.RANK.values()))
    assert len(ranks) >= 4, f"{ranks} is not a layering, it is a two-bucket sort"


@pytest.mark.parametrize(
    "module_path,imported",
    UPWARD,
    ids=[f"{p.split('/')[0].removesuffix('.py')}->{m.split('.')[1]}" for p, m in UPWARD],
)
def test_the_gate_refuses_each_upward_import(gate, sandbox, capsys, module_path, imported):
    offender = sandbox / module_path
    offender.write_text(
        offender.read_text(encoding="utf-8") + f"\nimport {imported}\n", encoding="utf-8"
    )
    code = gate.main()
    out = capsys.readouterr().out
    assert code == 1, f"{module_path} importing {imported} passed the gate:\n{out}"
    assert "upward import" in out
    assert imported in out, "a failure that does not name the import teaches nothing"


def test_an_unranked_module_fails_the_gate(gate, sandbox, capsys):
    """The tier decision is made when the package lands or not at all — a gate that
    shrugs at a name it does not know is how `render` stopped being checked."""
    newcomer = sandbox / "reporting"
    newcomer.mkdir()
    (newcomer / "__init__.py").write_text("")
    code = gate.main()
    out = capsys.readouterr().out
    assert code == 1, f"an unranked package passed the gate:\n{out}"
    assert "reporting" in out
    assert "bin/check-layers" in out, "the message has to say where the decision goes"


def test_the_package_passes_its_own_gate():
    """A red gate is one people learn to skip."""
    result = subprocess.run([sys.executable, str(GATE)], capture_output=True, text=True, cwd=ROOT)
    assert result.returncode == 0, result.stdout


def test_the_package_facade_outranks_every_layer_it_re_exports(gate):
    """`deckwright/__init__.py` imports from `compile` and `theme`, so ranking a bare `deckwright` at the
    bottom makes that an upward import and the gate refuses the package's own front door."""
    assert gate.rank("deckwright") == gate.FACADE
    assert gate.FACADE > max(gate.RANK.values())


def test_nothing_inside_the_package_reaches_back_through_the_facade(gate):
    """The converse the ranking buys: a module importing bare `deckwright` would be
    importing the thing that imports it."""
    assert gate.rank("deckwright") > gate.rank("deckwright.cli")
    assert gate.rank("deckwright.compile.build") == gate.RANK["compile"]
