"""One shape for "you named a key nobody declared"."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from deckwright.utils.text import closest_match

# Every declared field is snake_case, so a space means YAML split a flow mapping at an
# unquoted comma — and truncated the value with it.
_PROSE_HINT = " — a key that reads like prose is an unquoted comma; quote the value"


def prose_hint(key: str) -> str:
    return _PROSE_HINT if " " in str(key) else ""


def _named(key: object) -> str:
    """A key as the author would have typed it: a string quoted, a resolved scalar bare."""
    if isinstance(key, str):
        return repr(key)
    if isinstance(key, bool):
        return "true" if key else "false"
    return "null" if key is None else str(key)


def _yaml_hint(key: object) -> str:
    """Why a key is not a string: YAML resolved what the author typed into another type."""
    if isinstance(key, bool):
        spellings = "yes, on or true" if key else "no, off or false"
        read = f"an unquoted {spellings} as the boolean {_named(key)}"
    elif key is None:
        read = "an empty key, ~ or null as null"
    elif isinstance(key, (int, float)):
        read = f"{_named(key)} as a number"
    else:
        read = f"{_named(key)} as a {type(key).__name__}"
    return f" — YAML reads {read}; quote the key"


def unknown_field(
    key: object,
    known: Iterable[str],
    *,
    where: str | None = None,
    lead: str = "unknown field",
    label: str = "known fields",
    suggest: bool = False,
) -> str:
    """``lead`` and ``label`` carry the only wording that differs between callers.

    Without ``where`` the result is a fragment, for a caller prefixing its own sentence.
    """
    known = list(known)
    if isinstance(key, str):
        hint = prose_hint(key)
        # A key holding a space came from a comma, so the nearest spelling is not the answer.
        match = closest_match(key, known) if suggest and not hint else None
    else:
        hint, match = _yaml_hint(key), None
    body = (
        f"{lead} {_named(key)}; did you mean {match!r}?"
        if match
        else f"{lead} {_named(key)}; {label}: {', '.join(known)}"
    )
    return f"{where}: {body}{hint}" if where else f"{body}{hint}"


def refuse_unknown(
    keys: Iterable[Any],
    known: Iterable[str],
    *,
    error: type[Exception],
    where: str | None = None,
    lead: str = "unknown field",
    label: str = "known fields",
    suggest: bool = False,
) -> None:
    """Raise ``error`` naming the first of ``keys`` that ``known`` does not hold.

    Keys sort as text: YAML hands back dates, booleans and null beside strings, and
    those do not order against each other.
    """
    known = tuple(known)
    allowed = frozenset(known)
    unknown = sorted((k for k in keys if k not in allowed), key=str)
    if unknown:
        raise error(
            unknown_field(unknown[0], known, where=where, lead=lead, label=label, suggest=suggest)
        )
