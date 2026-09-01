"""One shape for "you named a key nobody declared"."""

from __future__ import annotations

from collections.abc import Iterable

from deckwright.utils.text import closest_match

# Every declared field is snake_case, so a space means YAML split a flow mapping at an
# unquoted comma — and truncated the value with it.
_PROSE_HINT = " — a key that reads like prose is an unquoted comma; quote the value"


def prose_hint(key: str) -> str:
    return _PROSE_HINT if " " in str(key) else ""


def unknown_field(
    key: str,
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
    # A key holding a space came from a comma, so the nearest spelling is not the answer.
    match = closest_match(key, known) if suggest and not prose_hint(key) else None
    body = (
        f"{lead} {key!r}; did you mean {match!r}?"
        if match
        else f"{lead} {key!r}; {label}: {', '.join(known)}"
    )
    return f"{where}: {body}{prose_hint(key)}" if where else f"{body}{prose_hint(key)}"
