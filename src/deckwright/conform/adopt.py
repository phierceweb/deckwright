"""Keep a derived theme, by moving it out of disposable output.

A conformance run writes under ``out/``, which is built to be deleted; adoption writes
the theme into the directory ``build`` resolves theme names from — beside the template
it binds to, which already lives there. Nothing is copied. The derivation is still the
first draft ``docs/conform.md`` says to edit.
"""

from __future__ import annotations

import filecmp
import re
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Any

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
        edits are carried through, an ``inverse`` lost in the page aside. ``force``
        is what discards them.
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
    if template.parent.resolve() != root.resolve():
        resident = root / template.name
        if resident.is_file():
            if filecmp.cmp(template, resident, shallow=False):
                raise ThemeError(
                    f"a template is adopted where it lives, and {root}/ already holds this "
                    f"one — adopt that copy: `deckwright conform {shlex.quote(str(resident))} "
                    f"--adopt {name}`"
                )
            raise ThemeError(
                f"a template is adopted where it lives, but {root}/ already holds a different "
                f"{template.name}, which moving this one in would overwrite — rename this one "
                f"before moving it into {root}/"
            )
        raise ThemeError(
            f"a template is adopted where it lives: move it into {root}/ first, then "
            f"adopt it from there — `mkdir -p {shlex.quote(str(root))} && mv "
            f"{shlex.quote(str(template))} {shlex.quote(str(root))}/` — so the "
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
    resolves from where it now lives rather than from the conform output. A theme already
    there keeps its comments and layout: only the lines whose values changed are
    rewritten, and a change that cannot be made that way rewrites the whole file.

    Returns:
        The installed theme file.
    """
    adoption.theme.parent.mkdir(parents=True, exist_ok=True)
    theme = yaml.safe_load(Path(derived).read_text(encoding="utf-8"))
    theme["name"] = adoption.name
    theme["template"] = adoption.template.name
    # Bytes, not text mode: reading text translates a CRLF file's line endings away.
    kept = adoption.theme.read_bytes().decode("utf-8") if adoption.theme.is_file() else None
    edited = None if kept is None else _edited(kept, theme)
    if edited is None:
        if kept is not None and re.search(r"(?m)^\s*#", kept):
            logger.warning("theme_comments_dropped", path=str(adoption.theme))
        adoption.theme.write_text(yaml.safe_dump(theme, sort_keys=False), encoding="utf-8")
    elif edited != kept:
        adoption.theme.write_bytes(edited.encode("utf-8"))

    logger.info("theme_adopted", name=adoption.name, path=str(adoption.theme))
    return adoption.theme


def _edited(text: str, theme: dict[str, Any]) -> str | None:
    """``text`` with only the values ``theme`` changes rewritten, or None.

    Covers top-level scalars and the scalars of a block-style ``bind:``; None for any other
    change, or for an edit that does not read back as ``theme`` with every key once.
    """
    try:
        kept = yaml.safe_load(text)
    except yaml.YAMLError:
        return None
    if kept == theme:
        return text
    if not isinstance(kept, dict):
        return None
    eol = "\r\n" if "\r\n" in text else "\n"
    lines: list[str] | None = text.replace("\r\n", "\n").splitlines(keepends=True)
    if lines and not lines[-1].endswith("\n"):
        lines[-1] += "\n"
    for key in dict.fromkeys([*kept, *theme]):
        old, new = kept.get(key), theme.get(key)
        if old == new or lines is None:
            continue
        if key == "bind" and isinstance(new, dict) and isinstance(old, dict | None):
            lines = _edit_block(lines, key, old or {}, new)
        elif key in kept and key in theme and not isinstance(old, dict | list):
            lines = _set_line(lines, range(len(lines)), "", key, new)
        else:
            return None
    if lines is None:
        return None
    out = "".join(lines).replace("\n", eol)
    try:
        return out if yaml.load(out, Loader=_UniqueKeys) == theme else None
    except yaml.YAMLError:
        return None


class _UniqueKeys(yaml.SafeLoader):
    """``SafeLoader`` refusing a repeated key, where PyYAML silently keeps the last."""


def _unique_mapping(loader: yaml.SafeLoader, node: yaml.MappingNode) -> dict[Any, Any]:
    keys = [loader.construct_object(key) for key, _ in node.value]
    if len({repr(k) for k in keys}) != len(keys):
        raise yaml.constructor.ConstructorError(None, None, "repeated key", node.start_mark)
    return loader.construct_mapping(node, deep=True)


_UniqueKeys.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _unique_mapping)


def _entry(indent: str, key: str, value: Any) -> str:
    return indent + yaml.safe_dump({key: value}, default_flow_style=False, width=1000)


def _key_at(lines: list[str], span: range, indent: str, key: str) -> int | None:
    pattern = re.compile(rf"{re.escape(indent)}{re.escape(key)}:(\s|$)")
    found = [i for i in span if pattern.match(lines[i])]
    return found[0] if len(found) == 1 else None


def _set_line(lines: list[str], span: range, indent: str, key: str, value: Any) -> list[str] | None:
    at = _key_at(lines, span, indent, key)
    if at is None:
        return None
    comment = re.search(r"\s+#.*$", lines[at].rstrip("\n"))
    entry = _entry(indent, key, value)
    if comment:
        entry = entry.rstrip("\n") + comment.group(0) + "\n"
    return [*lines[:at], entry, *lines[at + 1 :]]


def _edit_block(
    lines: list[str], block: str, old: dict[str, Any], new: dict[str, Any]
) -> list[str] | None:
    """A block-style mapping's changed scalars rewritten in place, its new ones appended."""
    if any(isinstance(v, dict | list) for v in (*old.values(), *new.values())):
        return None
    header = [i for i, line in enumerate(lines) if re.match(rf"{block}:\s*(#.*)?$", line)]
    if not header:
        if old:
            return None
        # An empty mapping written inline (`bind: {}`, `bind: ~`) is replaced, not repeated.
        at = _key_at(lines, range(len(lines)), "", block)
        entries = [f"{block}:\n", *(_entry("  ", k, v) for k, v in new.items())]
        return [*lines, *entries] if at is None else [*lines[:at], *entries, *lines[at + 1 :]]
    if len(header) > 1:
        return None
    end = header[0] + 1
    while end < len(lines) and (not lines[end].strip() or lines[end][0] in " \t#"):
        end += 1
    children = [
        i
        for i in range(header[0] + 1, end)
        if lines[i].strip() and not lines[i].lstrip().startswith("#")
    ]
    indent = "  "
    if children:
        first = lines[children[0]]
        indent = first[: len(first) - len(first.lstrip())]
    last = children[-1] + 1 if children else header[0] + 1
    for key in [k for k in old if k not in new]:
        at = _key_at(lines, range(header[0] + 1, end), indent, key)
        if at is None:
            return None
        lines = [*lines[:at], *lines[at + 1 :]]
        end, last = end - 1, last - 1
    added = []
    for key, value in new.items():
        if key not in old:
            added.append(_entry(indent, key, value))
        elif old[key] != value:
            changed = _set_line(lines, range(header[0] + 1, end), indent, key, value)
            if changed is None:
                return None
            lines = changed
    return [*lines[:last], *added, *lines[last:]]
