"""Run every QA check over a built deck and its manifest."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from pf_core.log import get_logger

from deckwright.errors import SpecError
from deckwright.paths import render_dir
from deckwright.qa.geometry import (
    check_bounds,
    check_placement_fit,
    check_contrast,
    check_reserved,
    check_text_fit,
    check_type_sizes,
)
from deckwright.qa.charts import check_charts
from deckwright.qa.fonts import check_faces
from deckwright.qa.imagery import check_render_contrast
from deckwright.qa.model import Finding, QaReport, Severity
from deckwright.qa.motion import check_beats, check_triggers
from deckwright.qa.package import check_package
from deckwright.qa.placeholder import check_placeholder
from deckwright.qa.report import write_json, write_markdown
from deckwright.qa.textflow import check_overflow, extract_pages
from deckwright.services.render import render_to_images
from deckwright.theme import load_theme
from deckwright.theme.model import Theme

logger = get_logger(__name__)


def _theme_file(
    given: str | Path | None, recorded: Any, manifest_path: Path, name: Any = None
) -> Path | str | None:
    """The theme to check against: the caller's, else the manifest's own.

    A recorded path is written relative to the manifest, so it resolves against the
    manifest rather than the working directory. An absolute one — an older manifest, or
    a build whose theme shared no ancestor with its output — is used as written.

    A deck handed over without its theme file still records the theme's *name*, and
    ``base`` is inside the package the recipient already has, so the name is tried
    before the missing path is reported.
    """
    if given:
        return Path(given)
    path: Path | None = None
    if recorded:
        path = Path(recorded)
        if not path.is_absolute():
            path = (manifest_path.parent / path).resolve()
        if path.is_file():
            return path
    if name:
        return str(name)
    return path


def _substituted_theme(theme: Theme, data: dict, resolved: Path | str) -> list[Finding]:
    """Warn when the theme that loaded is not the one the deck was built against.

    A name resolves against the *reader's* theme directory before the packaged ones, so
    a handed-over deck naming `brand` picks up whatever `brand` is on this machine. The
    palette, grid and rungs every other check reads then come from the wrong file.
    """
    recorded = str(data.get("theme_hash") or "")
    if isinstance(resolved, Path) or not recorded or recorded == theme.hash:
        return []
    return [
        Finding(
            slide=0,
            check="theme-substituted",
            severity=Severity.WARN,
            detail=(
                f"the deck was built against theme {str(data.get('theme'))!r} at "
                f"{str(data.get('theme_path'))!r}, which is not here; {resolved!r} "
                f"resolved to a different file (recorded {recorded}, loaded "
                f"{theme.hash}). Every finding below is measured against that other "
                f"theme — pass --theme to name the right one"
            ),
        )
    ]


def _stale_manifest(deck: Path, data: dict, manifest_path: Path) -> list[Finding]:
    """Does this manifest still describe this file?

    Every check below believes the manifest, so a deck hand-edited after the build makes
    the findings describe a file that is gone. A warning, not an error: the hand-edit is a
    sanctioned workflow.
    """
    recorded = data.get("deck_hash")
    if not recorded:
        return []
    actual = hashlib.sha256(deck.read_bytes()).hexdigest()[: len(recorded)]
    if actual == recorded:
        return []
    return [
        Finding(
            slide=0,
            check="stale-manifest",
            severity=Severity.WARN,
            detail=(
                f"{deck.name} has changed since it was built — {manifest_path.name} "
                f"records {recorded}, the file is {actual}. Every other finding below "
                f"describes the build, not this file; rebuild to check what you have"
            ),
        )
    ]


def run_qa(
    deck: str | Path,
    *,
    manifest: str | Path | None = None,
    theme_path: str | Path | None = None,
    render: bool = True,
    outdir: str | Path | None = None,
) -> QaReport:
    """Check ``deck`` against its manifest and, unless ``render`` is False, its render.

    Raises:
        SpecError: the manifest is missing or names no theme.
        ThemeError: the theme or its template cannot be loaded.
        RenderError: the render or text extraction failed.
    """
    deck = Path(deck)
    manifest_path = Path(manifest) if manifest else deck.with_suffix(".manifest.json")
    if not manifest_path.is_file():
        raise SpecError(f"manifest not found: {manifest_path} — build the deck first")
    data = json.loads(manifest_path.read_text(encoding="utf-8"))

    theme_file = _theme_file(theme_path, data.get("theme_path"), manifest_path, data.get("theme"))
    if not theme_file:
        raise SpecError(f"{manifest_path.name}: no theme_path recorded — pass --theme")
    theme = load_theme(theme_file)

    findings: list[Finding] = []
    findings.extend(_substituted_theme(theme, data, theme_file))
    findings.extend(_stale_manifest(deck, data, manifest_path))
    if not data.get("slides"):
        findings.append(
            Finding(
                slide=0,
                check="empty-manifest",
                severity=Severity.WARN,
                detail=f"{manifest_path.name} records no slides — nothing was checked",
            )
        )
    for check in (
        check_bounds,
        check_placement_fit,
        check_reserved,
        check_type_sizes,
        check_contrast,
        check_text_fit,
        check_placeholder,
        check_beats,
    ):
        findings.extend(check(data, theme))
    # These three read the saved package: a hand-edit after the build leaves the manifest
    # describing a file that is gone.
    findings.extend(check_package(deck))
    findings.extend(check_charts(deck))
    findings.extend(check_triggers(deck))

    out = Path(outdir) if outdir else render_dir(deck)
    if render:
        findings.extend(check_faces(data, theme))
        images = render_to_images(deck, out)
        pdf = out / f"{deck.stem}.pdf"
        findings.extend(
            check_overflow(data, extract_pages(pdf), extract_pages(pdf, layout=True), pdf_path=pdf)
        )
        findings.extend(check_render_contrast(data, images))
        logger.info("qa_rendered", slides=len(images))

    findings.sort(key=lambda f: (f.slide, -f.severity.rank, f.check))
    report = QaReport(deck=str(deck), findings=tuple(findings))
    write_markdown(report, out / "qa.md")
    write_json(report, out / "qa.json")
    logger.info("qa_done", deck=str(deck), findings=len(findings))
    return report
