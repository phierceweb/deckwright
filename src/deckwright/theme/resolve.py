"""Find a theme file by name or path — the theme directory, then the packaged built-ins.

Config (env, read at call time, so ``.env`` changes take effect between runs):

- ``DECKWRIGHT_THEME_DIR`` — directory holding templates and their themes (default ``templates``).
"""

from __future__ import annotations

from importlib import resources
from pathlib import Path

from deckwright.errors import ThemeError
from deckwright.utils.env import env_str

_THEME_DIR_DEFAULT = "templates"
_THEME_DIR_ENV_VAR = "DECKWRIGHT_THEME_DIR"


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
