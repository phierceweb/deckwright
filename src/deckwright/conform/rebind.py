"""Repair a kept theme's ``inverse`` when it vanishes into the page, leaving every other key."""

from __future__ import annotations

from pathlib import Path

from deckwright.conform.derive import _DARK_SLOTS, _inverse, _inverse_ink, master_scheme
from deckwright.theme.defaults import DEFAULT_ROLES
from deckwright.utils.color import AA_LARGE, contrast_ratio
from deckwright.utils.deck import open_presentation


def scheme_of(template: str | Path, *, prefer: str | None = None) -> dict[str, str]:
    """The colour scheme of the master ``template``'s slides compose on."""
    return master_scheme(open_presentation(template), prefer=prefer)


def rebound_inverse(
    scheme: dict[str, str], bind: dict[str, str]
) -> tuple[dict[str, str], str] | None:
    """``bind`` with ``inverse`` and ``inverse-ink`` derived afresh, and what changed.

    None unless the kept ``inverse``, bound or default, stands under 3:1 off ``page`` and a
    slot clears it.
    """
    if not any(s in scheme for s in _DARK_SLOTS):
        return None

    def hex_of(role: str) -> str:
        value = str(bind.get(role, DEFAULT_ROLES[role]))
        return scheme.get(value, value)

    page = hex_of("page")
    before = contrast_ratio(hex_of("inverse"), page)
    if before >= AA_LARGE:
        return None
    inverse = _inverse(scheme, page=page)
    after = contrast_ratio(scheme[inverse], page)
    if after < AA_LARGE:
        return None
    rebound = dict(bind, inverse=inverse)
    rebound.pop("inverse-ink", None)
    ink = _inverse_ink(scheme, inverse=scheme[inverse])
    if ink is not None:
        rebound["inverse-ink"] = ink
    was = bind.get("inverse", f"{DEFAULT_ROLES['inverse']} (default)")
    return rebound, f"inverse {was} -> {inverse}: {before:.1f}:1 off the page, now {after:.1f}:1"
