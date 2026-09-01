"""Keep a derived theme, by moving it out of disposable output.

A conformance run writes under ``out/``, which is built to be deleted; adoption writes
the theme into the directory ``build`` resolves theme names from — beside the template
it binds to, which already lives there. Nothing is copied. The derivation is still the
first draft ``docs/conform.md`` says to edit.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from pf_core.log import get_logger

from deckwright.compile.build import theme_dir
from deckwright.errors import ThemeError

logger = get_logger(__name__)

_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")


@dataclass(frozen=True)
class Adoption:
    """Where an adopted theme will land, and the template it will bind to."""

    name: str
    theme: Path
    template: Path


def plan(name: str, template: str | Path, *, force: bool = False) -> Adoption:
    """Resolve and vet where adopting ``template`` as ``name`` would write.

    Args:
        name: Bare theme name — what a deck spec's ``theme:`` will say.
        template: The brand ``.pptx`` being adopted.
        force: Re-derive over an existing theme of this name, discarding its edits.

    Returns:
        The vetted destination, for :func:`install` to write.

    Raises:
        ThemeError: ``name`` is not a bare theme name, the template is missing, the
            template does not live in the theme directory, or the name is already
            bound to a different template.

    Note:
        Re-adopting the *same* template under the same name is a refresh, not a
        clobber: the theme file beside the template is this run's sidecar, so its
        edits are carried through verbatim. ``force`` is what discards them.
    """
    template = Path(template)
    if not _NAME.fullmatch(name):
        raise ThemeError(
            f"--adopt takes a bare theme name — letters, digits, '-' and '_' — got "
            f"{name!r}; it becomes <theme dir>/<name>.theme.yaml and a deck's 'theme:' line"
        )
    if not template.is_file():
        raise ThemeError(f"template not found: {template}")

    root = theme_dir()
    dest = root / f"{name}.theme.yaml"
    # The theme binds to the template by a bare filename resolved beside it, so the
    # binary has to already be here.
    if template.resolve().parent != root.resolve():
        raise ThemeError(
            f"a template is adopted where it lives: move it into {root}/ first, then "
            f"adopt it from there — `mkdir -p {root} && mv {template} {root}/` — so the "
            f"theme sits beside its own binary and there is only ever one copy of it"
        )
    if dest.exists() and not force:
        bound = str(
            (yaml.safe_load(dest.read_text(encoding="utf-8")) or {}).get("template", "")
        ).strip()
        # A stale pointer is what `install` exists to rewrite; a pointer at a template
        # that is really here is a live binding, and repointing it hijacks that theme.
        if bound and bound != template.name and (root / bound).is_file():
            raise ThemeError(
                f"theme {name!r} already exists at {dest} and binds {bound!r}, which is "
                f"also here — adopt {template.name} under another name, or pass --force "
                f"to repoint it; any edits made to it are not recoverable"
            )
    return Adoption(name=name, theme=dest, template=template)


def install(adoption: Adoption, derived: str | Path) -> Path:
    """Write the derived theme into the theme directory, beside its template.

    The theme is renamed and re-pointed at the template by bare filename, so it
    resolves from where it now lives rather than from the conform output.

    Returns:
        The installed theme file.
    """
    adoption.theme.parent.mkdir(parents=True, exist_ok=True)
    theme = yaml.safe_load(Path(derived).read_text(encoding="utf-8"))
    theme["name"] = adoption.name
    theme["template"] = adoption.template.name
    adoption.theme.write_text(yaml.safe_dump(theme, sort_keys=False), encoding="utf-8")

    logger.info("theme_adopted", name=adoption.name, path=str(adoption.theme))
    return adoption.theme
