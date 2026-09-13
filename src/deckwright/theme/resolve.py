"""Find a theme file by name or path — the theme directory, then the packaged built-ins.

Config (env, read at call time, so ``.env`` changes take effect between runs):

- ``DECKWRIGHT_THEME_DIR`` — directory holding templates and their themes (default ``templates``).
"""

from __future__ import annotations

import filecmp
import shlex
from importlib import resources
from pathlib import Path

import yaml

from deckwright.errors import ThemeError
from deckwright.utils.env import env_str
from deckwright.utils.naming import slug_and_title

_THEME_DIR_DEFAULT = "templates"
_THEME_DIR_ENV_VAR = "DECKWRIGHT_THEME_DIR"
_TEMPLATE_SUFFIXES = (".pptx", ".potx", ".pptm")


def theme_dir() -> Path:
    """Directory holding brand templates and the themes bound to them.

    A theme's ``template:`` resolves relative to the theme file, so both live here and
    the binary is never copied. Read at call time, not import time.
    """
    root = env_str(None, _THEME_DIR_ENV_VAR, default=_THEME_DIR_DEFAULT)
    return Path(root)


def resolve_theme(name: str) -> Path:
    """``<theme_dir>/<name>.theme.yaml``, falling back to the packaged built-in themes.

    A name found in neither place returns the theme-dir candidate, so the not-found
    error names the directory the caller controls.
    """
    candidate = theme_dir() / f"{name}.theme.yaml"
    if candidate.is_file():
        return candidate
    builtin = _builtin_dir() / f"{name}.yaml"
    return builtin if builtin.is_file() else candidate


def _builtin_dir() -> Path:
    return Path(str(resources.files("deckwright"))) / "theme" / "builtin"


def theme_file(ref: str | Path) -> Path:
    """An existing file for a theme name or a theme path, or a ThemeError saying which."""
    path = Path(ref)
    if path.suffix.lower() in _TEMPLATE_SUFFIXES:
        raise ThemeError(_template_route(path))
    if path.is_file():
        return path
    if path.suffix or len(path.parts) > 1:
        raise ThemeError(
            f"theme file not found: {path} — that is read as a path, and nothing is "
            f"searched. To load a theme by name, pass the bare name (e.g. 'base'), "
            f"which is looked up in {theme_dir()} and then in the packaged themes"
        )
    resolved = resolve_theme(str(ref))
    if resolved.is_file():
        return resolved
    packaged = ", ".join(sorted(p.stem for p in _builtin_dir().glob("*.yaml")))
    raise ThemeError(
        f"unknown theme {str(ref)!r}: no theme file at {resolved} (set "
        f"DECKWRIGHT_THEME_DIR to search elsewhere) and no packaged theme of that name "
        f"(packaged: {packaged}). Onboard a brand template with "
        f"'deckwright conform <brand>.pptx --adopt {ref}', or pass a path to a theme file"
    )


def _template_route(ref: Path) -> str:
    """What to build with instead of a ``theme:`` that names a template."""
    root = theme_dir()
    found = ref if ref.is_file() else root / ref.name
    slug, _ = slug_and_title(ref.stem, fallback="brand")
    if not found.is_file():
        return (
            f"{ref} names a template, not a theme, and there is no file at {ref} or in {root}/ "
            f"— put it in {root}/, onboard it once with "
            f"`deckwright conform {shlex.quote(str(root / ref.name))} --adopt {slug}`, then "
            f"build with 'theme: {slug}'"
        )
    adopted = _adopted_as(found)
    if adopted:
        names = " or ".join(f"'theme: {name}'" for name in adopted)
        return (
            f"{found.name} is a template, not a theme, and it is already adopted — build "
            f"with {names}"
        )
    command = f"deckwright conform {shlex.quote(str(root / found.name))} --adopt {slug}"
    # The directory, not the file: a symlink in the theme dir lives there.
    if found.parent.resolve() != root.resolve():
        resident = root / found.name
        if resident.is_file():
            if filecmp.cmp(found, resident, shallow=False):
                return _template_route(resident)
            adopted = _adopted_as(resident)
            known = f", adopted as {' or '.join(repr(n) for n in adopted)}," if adopted else ""
            return (
                f"{found.name} is a template, not a theme, and {root}/ already holds a "
                f"different {found.name}{known} which moving this one in would overwrite — "
                f"rename this one before onboarding it from {root}/"
            )
        # `conform --adopt` refuses a template outside the theme dir.
        command = (
            f"mkdir -p {shlex.quote(str(root))} && mv {shlex.quote(str(found))} "
            f"{shlex.quote(str(root))}/ && {command}"
        )
    return (
        f"{found.name} is a template, not a theme — onboard it once with `{command}`, then "
        f"build with 'theme: {slug}'"
    )


def _adopted_as(template: Path) -> list[str]:
    """The names of the themes in the theme dir already bound to ``template``."""
    names = []
    for theme in sorted(theme_dir().glob("*.theme.yaml")):
        try:
            data = yaml.safe_load(theme.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, yaml.YAMLError):
            continue
        bound = data.get("template") if isinstance(data, dict) else None
        if bound and (theme.parent / str(bound)).resolve() == template.resolve():
            names.append(theme.name.removesuffix(".theme.yaml"))
    return names
