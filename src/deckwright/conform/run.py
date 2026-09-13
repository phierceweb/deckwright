"""Drive a brand template through every component and report what breaks.

One slide at a time, so a component that fails names itself instead of taking the
whole run down with it.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from pf_core.log import get_logger

from deckwright.compile.build import build_deck
from deckwright.conform.adopt import install, plan
from deckwright.conform.derive import derive, notes
from deckwright.conform import assemble
from deckwright.conform.exercise import EXERCISE
from deckwright.conform.rebind import rebound_inverse, scheme_of
from deckwright.errors import LayoutError, MissingToolError, RenderError, SpecError, ThemeError
from deckwright.paths import scratch

logger = get_logger(__name__)

_EXPECTED = (ThemeError, SpecError, LayoutError, MissingToolError, RenderError)


@dataclass
class Conformance:
    """What a template could and could not do."""

    template: str
    notes: list[str] = field(default_factory=list)
    passed: list[str] = field(default_factory=list)
    failed: list[tuple[str, str]] = field(default_factory=list)
    deck: Path | None = None
    theme: Path | None = None
    adopted: Path | None = None
    refused: str | None = None

    @property
    def ok(self) -> bool:
        return not self.failed

    def report(self) -> str:
        lines = [f"{self.template}", *(f"  · {n}" for n in self.notes)]
        for name in self.passed:
            lines.append(f"  ok    {name}")
        for name, why in self.failed:
            lines.append(f"  FAIL  {name}: {why}")
        lines.append(f"  {len(self.passed)}/{len(self.passed) + len(self.failed)} exercises")
        if self.refused:
            lines.append(f"  not adopted: {self.refused}")
        return "\n".join(lines)


def _pointer(template: Path, outdir: Path) -> str:
    """How a theme written into ``outdir`` reaches ``template``.

    A relative path back to the template where it already lives. The run does not copy
    it: a second copy is a second name waiting to drift from the first.
    """
    return os.path.relpath(template.resolve(), outdir.resolve())


def _write_theme_file(theme: dict, template: Path, outdir: Path) -> Path:
    outdir.mkdir(parents=True, exist_ok=True)
    theme["template"] = _pointer(template, outdir)
    path = outdir / f"{template.stem[:40]}.theme.yaml"
    path.write_text(yaml.safe_dump(theme, sort_keys=False), encoding="utf-8")
    return path


def _copy_sidecar(
    sidecar: Path, template: Path, outdir: Path, *, prefer: str | None, rebind: bool
) -> tuple[Path, str | None]:
    """Bring a kept theme into the run, pointed back at the template it binds to.

    Verbatim, but for an ``inverse`` that vanishes into the page: ``rebind`` derives it
    afresh, otherwise the returned note only says so.
    """
    theme = yaml.safe_load(sidecar.read_text(encoding="utf-8"))
    bind = theme.get("bind") or {}
    # A malformed `bind:` is left for the theme loader to refuse by name.
    repair = (
        rebound_inverse(scheme_of(template, prefer=prefer), bind)
        if isinstance(bind, dict)
        else None
    )
    note = None
    if repair is not None:
        bind, change = repair
        if rebind:
            theme["bind"] = bind
            note = f"rebound {change}"
        else:
            note = f"{change} — re-adopting rebinds it"
    return _write_theme_file(theme, template, outdir), note


def _write_theme(template: Path, outdir: Path, *, prefer: str | None = None) -> Path:
    """Derive a theme into ``outdir``, pointed back at the template it was read from."""
    return _write_theme_file(derive(template, prefer=prefer), template, outdir)


def conform(
    template: str | Path,
    outdir: str | Path,
    *,
    exercises: dict[str, dict[str, Any]] | None = None,
    theme: str | Path | None = None,
    adopt: str | None = None,
    force: bool = False,
) -> Conformance:
    """Build every exercise against ``template``, reporting each one's fate.

    Args:
        template: The brand ``.pptx`` to drive.
        outdir: Where the derived theme, the combined deck and the run's scratch go.
        exercises: A subset to run, for iterating on one slide. Defaults to all.
        theme: An existing theme to drive with, instead of deriving one — how an
            already-onboarded template is exercised as its decks actually load it.
        adopt: Keep the derived theme as ``<theme dir>/<adopt>.theme.yaml`` — see
            :mod:`deckwright.conform.adopt`. Refused if nothing built.
        force: With ``adopt``, replace an existing theme of that name.

    Raises:
        ThemeError: the template is missing, is not a readable .pptx, or cannot yield
            a theme — nothing can be built — or the adoption target is unusable.
    """
    template = Path(template)
    outdir = Path(outdir)
    if not template.is_file():
        raise ThemeError(f"template not found: {template}")
    # Vetted before the exercises: a name collision is worth knowing now, not at the
    # end of a run it should have prevented.
    adoption = plan(adopt, template, force=force) if adopt else None
    work = scratch(outdir)
    # The sidecar and the adoption target are one file, so re-adopting keeps your
    # edits; --force discards them.
    sidecar = (
        Path(theme)
        if theme
        else (template.with_name(f"{adopt}.theme.yaml") if adopt and not force else None)
    )
    # Read before anything resolves a layout: `compose_layout:` is the only thing that
    # settles a template whose emptiest layouts disagree, so --force never discards it.
    standing = template.with_name(f"{adopt}.theme.yaml") if adopt else None
    prefer = None
    for candidate in (sidecar, standing):
        if candidate is not None and candidate.is_file():
            prefer = (yaml.safe_load(candidate.read_text(encoding="utf-8")) or {}).get(
                "compose_layout"
            )
            if prefer:
                break
    tuned = sidecar if sidecar is not None and sidecar.is_file() else None
    repaired = None
    if tuned is not None:
        # The exercises run against the sidecar, so what is validated is what is
        # installed.
        theme_path, repaired = _copy_sidecar(
            tuned, template, outdir, prefer=prefer, rebind=adoption is not None
        )
    else:
        theme_path = _write_theme(template, outdir, prefer=prefer)
    written = yaml.safe_load(theme_path.read_text(encoding="utf-8"))
    bound = written.get("bind")
    result = Conformance(
        template=template.name,
        notes=notes(template, bind=bound if isinstance(bound, dict) else {}, prefer=prefer),
    )
    if tuned is not None:
        result.notes.append(f"theme from sidecar {tuned.name} — tuned, not derived")
    if repaired is not None:
        result.notes.append(repaired)
    result.theme = theme_path
    theme_name = written["name"]

    kit = assemble.assets(work)

    kept: list[dict[str, Any]] = []
    for name, slide in (exercises or EXERCISE).items():
        spec_path = work / f"_{name}.deck.yaml"
        out = work / f"_{name}.pptx"
        spec_path.write_text(
            assemble.fill(assemble.spec([slide], theme=theme_name, out=out.name), kit),
            encoding="utf-8",
        )
        try:
            build_deck(spec_path, theme_path=theme_path, out=out)
        except _EXPECTED as e:
            # Left where it fell: a FAIL line is worth more beside the spec that
            # produced it.
            result.failed.append((name, str(e).replace("\n", " ")[:180]))
            continue
        result.passed.append(name)
        kept.append(slide)
        spec_path.unlink(missing_ok=True)
        out.unlink(missing_ok=True)
        # The manifest is written beside the deck, so it outlives it unless said so.
        out.with_suffix(".manifest.json").unlink(missing_ok=True)

    if kept:
        whole = outdir / f"{template.stem[:40]}.deck.yaml"
        deck = outdir / f"{template.stem[:40]}.pptx"
        whole.write_text(
            assemble.fill(assemble.spec(kept, theme=theme_name, out=deck.name), kit),
            encoding="utf-8",
        )
        build_deck(whole, theme_path=theme_path, out=deck)
        result.deck = deck

    if adoption is not None:
        # A FAIL is one capability this template cannot carry; nothing passing is a
        # different claim — the theme is wrong.
        if result.passed:
            result.adopted = install(adoption, theme_path)
        else:
            result.refused = (
                f"no exercise built, so the derived theme does not "
                f"describe {template.name} — read {theme_path} and fix "
                f"its bind: before adopting"
            )
    logger.info(
        "conformed",
        template=template.name,
        passed=len(result.passed),
        failed=len(result.failed),
        adopted=str(result.adopted or ""),
    )
    return result
