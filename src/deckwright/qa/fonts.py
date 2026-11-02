"""Whether the machine that rendered this deck actually had the theme's faces."""

from __future__ import annotations

from typing import Any

from deckwright.qa.model import Finding, Severity
from deckwright.theme.fonts import installed_families, missing_faces
from deckwright.theme.model import Theme


def check_faces(manifest: dict[str, Any], theme: Theme) -> list[Finding]:
    """Flag each face the theme names that this machine cannot set."""
    installed = installed_families()
    if installed is None:
        return []
    return [
        Finding(
            slide=0,
            check="font-substituted",
            severity=Severity.WARN,
            detail=(
                f"theme {theme.name!r} sets type in {face!r}, which is not installed here — "
                f"the render substituted something else, so `overflow` and `render-contrast` "
                f"judged a deck your audience will not see. Install the face, or read those "
                f"two findings as approximate"
            ),
        )
        for face in missing_faces(theme, installed)
    ]
