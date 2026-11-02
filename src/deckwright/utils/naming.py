"""A deck's directory name, display title and filename — one answer for every command."""

from __future__ import annotations

import re

from deckwright.errors import SpecError

# Wide enough that PyYAML never folds a long title across two lines.
NO_FOLD = 10_000

_NOT_IN_A_SLUG = re.compile(r"[^a-z0-9]+")
_NOT_IN_A_FILENAME = re.compile(r"[/\\:]")


def slug_and_title(name: str, *, fallback: str | None = None) -> tuple[str, str]:
    """A deck's directory name and display title, from whichever was typed.

    Case past the first letter is kept, so ``ML-pipeline`` is *ML Pipeline*, not the
    *Ml Pipeline* ``str.title`` gives. The slug keeps letters and digits only, so a
    name carrying a slash or a ``..`` cannot steer the write out of the deck root.

    Raises:
        SpecError: nothing in ``name`` survives slugging and no ``fallback`` was given.
    """
    words = [w for w in re.split(r"[\s_-]+", name.strip()) if w]
    slug = "-".join(p for p in (_NOT_IN_A_SLUG.sub("", w.lower()) for w in words) if p)
    if not slug:
        if fallback is None:
            raise SpecError(f"a deck needs a name, got {name!r}")
        slug = fallback
    return slug, " ".join(w[:1].upper() + w[1:] for w in words)


def deck_filename(title: str) -> str:
    """``title`` as a leaf filename: the separators a path would read are folded out."""
    return _NOT_IN_A_FILENAME.sub("-", title)
