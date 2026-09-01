"""Typed narrowing over pf-core's env resolvers.

``resolve_str`` returns ``str | None`` because its ``default`` is optional. Every
deckwright knob passes a real default, so the result is never None — this pins that
for the type checker without restating the default at each call site.
"""

from __future__ import annotations

from pf_core.utils.env import resolve_str


def env_str(arg: str | None, env_var: str, *, default: str) -> str:
    """``resolve_str`` for a knob that always has a default."""
    value = resolve_str(arg, env_var, default=default)
    return default if value is None else value
