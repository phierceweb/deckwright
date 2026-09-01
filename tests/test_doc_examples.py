"""Every YAML example in the docs has to be the thing it looks like: an unquoted comma inside a flow
mapping starts a **new key**, so `body: A divider, weighted off the theme.` is two keys and the
build rejects it. The docs gate reads vocabularies and file paths, never the examples themselves."""

from __future__ import annotations

import pathlib
import re

import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
# Every doc a reader copies from. errors.md is deliberately excluded: its blocks are
# broken on purpose, being the messages a broken spec produces.
DOCS = sorted(p for p in ROOT.glob("docs/*.md") if p.name != "errors.md")
DOCS += [ROOT / "README.md", ROOT / "CLAUDE.md"]

_BLOCK = re.compile(r"```yaml\n(.*?)```", re.S)


def _blocks() -> list[tuple[str, int, str]]:
    found = []
    for doc in DOCS:
        if not doc.is_file():
            continue
        text = doc.read_text()
        for match in _BLOCK.finditer(text):
            line = text[: match.start()].count("\n") + 1
            found.append((doc.relative_to(ROOT).as_posix(), line, match.group(1)))
    return found


BLOCKS = _blocks()


def test_the_docs_carry_examples_to_check():
    """Guards the parametrization: a regex that stops matching would empty every test
    below and leave them all green."""
    assert len(BLOCKS) > 40


def _dangling(node) -> list[str]:
    """Keys that parsed with no value and read like prose — the comma signature. A real key is one
    word; `weighted off the theme.` is several and empty."""
    out: list[str] = []
    if isinstance(node, dict):
        for key, value in node.items():
            if value is None and isinstance(key, str) and len(key.split()) > 1:
                out.append(key)
            out.extend(_dangling(value))
    elif isinstance(node, list):
        for item in node:
            out.extend(_dangling(item))
    return out


@pytest.mark.parametrize("doc,line,block", BLOCKS, ids=[f"{d}:{n}" for d, n, _ in BLOCKS])
def test_no_example_hides_a_comma_split_mapping(doc, line, block):
    """The defect itself: prose containing a comma, unquoted inside a flow mapping."""
    try:
        parsed = list(yaml.safe_load_all(block))
    except yaml.YAMLError:
        pytest.skip(f"{doc}:{line} is not standalone YAML")
    dangling = _dangling(parsed)
    assert dangling == [], (
        f"{doc}:{line}: {dangling} parsed as empty keys — an unquoted comma split a "
        f'flow mapping. Quote the value: body: "A divider, weighted off the theme."'
    )


def test_the_documented_python_entry_point_works():
    """README and `deckwright/__init__.py` both show `import deckwright; deckwright.build_deck`, and the
    package ships `py.typed`, so a caller is invited to import it."""
    import deckwright

    for name in deckwright.__all__:
        assert hasattr(deckwright, name), f"__all__ promises {name}, which is not there"
    assert deckwright.__version__
    assert callable(deckwright.build_deck)


def test_building_from_python_produces_the_same_deck_as_the_cli(tmp_path):
    """The README example, run. A facade that re-exports a function nobody calls
    through it is worth nothing."""
    import deckwright

    spec = tmp_path / "d.deck.yaml"
    spec.write_text("theme: base\nout: D.pptx\n---\ntitle: Hello\n")
    result = deckwright.build_deck(spec)
    assert isinstance(result, deckwright.BuildResult)
    assert result.slides == 1
    assert result.deck.is_file() and result.manifest.is_file()
