"""Package part names: where a part's relationships live, and where a relationship points."""

from __future__ import annotations


def rels_part(part: str) -> str:
    """The relationship part that belongs to ``part``."""
    folder, _, name = part.rpartition("/")
    return f"{folder}/_rels/{name}.rels"


def resolve(part: str, target: str) -> str:
    """A relationship target as a package name, resolved against the part that declares it.

    A target starting with ``/`` names the part from the package root.
    """
    base = [] if target.startswith("/") else part.rsplit("/", 1)[0].split("/")
    for step in target.split("/"):
        if step == "..":
            base = base[:-1]
        elif step not in ("", "."):
            base = [*base, step]
    return "/".join(base)
