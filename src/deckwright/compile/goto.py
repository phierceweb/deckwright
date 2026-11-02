"""Write each ``goto:`` as a click action, once every slide it can name exists.

A named slide is a ``hlinksldjump`` with a relationship to that slide's part. A relative
jump is a ``hlinkshowjump`` and relates to nothing, which PowerPoint writes as ``r:id=""``.
"""

from __future__ import annotations

from typing import Any

from pptx.oxml.ns import qn

_SHOW_JUMP = {
    "first": "firstslide",
    "previous": "previousslide",
    "next": "nextslide",
    "last": "lastslide",
}


def write_gotos(gotos: list[tuple[Any, str]], *, slides: dict[str, Any]) -> None:
    """Make each shape jump to its target: a slide id in ``slides``, or a relative jump.

    Targets are validated at parse, so a name missing from ``slides`` is a bug here.
    """
    for shape, target in gotos:
        if target in _SHOW_JUMP:
            hlink = shape._element._nvXxPr.cNvPr.get_or_add_hlinkClick()
            hlink.set(qn("r:id"), "")
            hlink.action = f"ppaction://hlinkshowjump?jump={_SHOW_JUMP[target]}"
        else:
            shape.click_action.target_slide = slides[target]
