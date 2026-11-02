"""What a built distribution is allowed to contain.

`.gitignore` keeps brand material out of the *repo*. It does nothing for a *dist*:
`python -m build` packs the working tree, so a `.pptx` anywhere a graft reaches, or the
framework docs link under `docs/`, ships unless MANIFEST.in says otherwise. These pin that
layer, so `pip install git+https://…` and any local build stay clean.
"""

from __future__ import annotations

import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "MANIFEST.in"

#: Directory `graft docs` would otherwise sweep up, and the rule that must exclude it.
PRIVATE = (
    ("docs/pw-foundation", "prune docs/pw-foundation"),
    ("docs/pf-core", "prune docs/pf-core"),
)


@pytest.mark.skipif(not MANIFEST.exists(), reason="no MANIFEST.in — running from an sdist")
@pytest.mark.parametrize("directory,rule", PRIVATE, ids=lambda v: v.split()[-1])
def test_manifest_excludes_a_private_directory_the_graft_would_reach(directory, rule):
    """Delete the rule and the next `python -m build` ships the contents."""
    assert rule in MANIFEST.read_text().splitlines(), (
        f"MANIFEST.in must carry {rule!r}: {directory} is gitignored, which does not "
        f"exclude it from a build"
    )


@pytest.mark.skipif(not MANIFEST.exists(), reason="no MANIFEST.in — running from an sdist")
def test_manifest_excludes_office_files_everywhere():
    """A brand template is a `.pptx`, and it can be dropped anywhere a graft reaches."""
    line = next(
        (ln for ln in MANIFEST.read_text().splitlines() if ln.startswith("global-exclude")), ""
    )
    assert "*.pptx" in line and "*.potx" in line, line


@pytest.mark.skipif(not (ROOT / ".git").exists(), reason="not a checkout")
def test_no_brand_material_is_tracked():
    """The first layer, restated as a test: `git ls-files` is the honest check, not
    `git status`, because .gitignore does not untrack what is already committed."""
    import subprocess

    tracked = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.split()
    offenders = [
        f
        for f in tracked
        if f.endswith((".pptx", ".potx"))
        or (f.startswith("templates/") and f != "templates/README.md")
    ]
    assert offenders == [], offenders
