"""Turn an SVG path's ``d`` attribute into DrawingML path commands.

Arcs become cubic béziers rather than ``a:arcTo``: SVG parameterizes an arc by its
endpoint and DrawingML by its sweep, so the conversion has a second chance at a sign
error for no gain.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

from deckwright.errors import SpecError

# The logical grid a path is emitted on. Large enough that rounding to integers is
# invisible at any size an icon is drawn.
UNITS = 100_000

# Any letter, not only the known commands: matching just the known ones would drop an
# unknown command silently and draw a truncated path rather than say what it hit.
_TOKEN = re.compile(r"[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?|[A-Za-z]")
_ARGS = {"M": 2, "L": 2, "H": 1, "V": 1, "C": 6, "S": 4, "Q": 4, "T": 2, "A": 7, "Z": 0}
# An arc is split so no bézier segment spans more than a quarter turn, which is where
# the cubic approximation stays within a fraction of a unit of the true curve.
_MAX_SWEEP = math.pi / 2


@dataclass(frozen=True)
class Command:
    """One DrawingML path command: its tag and the points it carries."""

    tag: str  # moveTo | lnTo | cubicBezTo | close
    points: tuple[tuple[float, float], ...] = ()


def parse(d: str) -> list[Command]:
    """Every drawing command in an SVG ``d`` attribute, in user units.

    Raises:
        SpecError: the data is malformed — an unknown command, or a command whose
            arguments run out partway.
    """
    tokens = _TOKEN.findall(d or "")
    out: list[Command] = []
    start = current = (0.0, 0.0)
    control: tuple[float, float] | None = None  # reflected control of the last curve
    letter = ""
    i = 0
    while i < len(tokens):
        # A repeated argument set implies the previous command, and a repeated moveto
        # implies lineto — the one case where the letter is not the command.
        if tokens[i].isalpha():
            letter = tokens[i]
            i += 1
        elif not letter:
            raise SpecError(f"svg path starts with a number, not a command: {d[:40]!r}")
        upper = letter.upper()
        try:
            count = _ARGS[upper]
        except KeyError:
            raise SpecError(f"unknown svg path command {letter!r}") from None
        args = tokens[i : i + count]
        if len(args) < count:
            raise SpecError(f"svg path command {letter!r} wants {count} numbers, got {len(args)}")
        i += count
        current, control = _step(
            out,
            upper,
            letter.islower(),
            [float(a) for a in args],
            current=current,
            control=control,
            start=start,
        )
        if upper == "M":
            start = current
            letter = "l" if letter.islower() else "L"
        elif upper == "Z":
            current = start
    return out


def _step(out, upper, relative, args, *, current, control, start):
    """Append the commands one SVG instruction becomes; return the new pen state."""
    x, y = current

    def point(dx, dy):
        return (x + dx, y + dy) if relative else (dx, dy)

    if upper == "M":
        current = point(*args)
        out.append(Command("moveTo", (current,)))
        return current, None
    if upper == "L":
        current = point(*args)
        out.append(Command("lnTo", (current,)))
        return current, None
    if upper == "H":
        current = (x + args[0] if relative else args[0], y)
        out.append(Command("lnTo", (current,)))
        return current, None
    if upper == "V":
        current = (x, y + args[0] if relative else args[0])
        out.append(Command("lnTo", (current,)))
        return current, None
    if upper == "C":
        c1, c2, end = point(*args[0:2]), point(*args[2:4]), point(*args[4:6])
        out.append(Command("cubicBezTo", (c1, c2, end)))
        return end, c2
    if upper == "S":
        c1 = _reflect(control, current)
        c2, end = point(*args[0:2]), point(*args[2:4])
        out.append(Command("cubicBezTo", (c1, c2, end)))
        return end, c2
    if upper == "Q":
        ctrl, end = point(*args[0:2]), point(*args[2:4])
        out.append(Command("cubicBezTo", _elevate(current, ctrl, end)))
        return end, ctrl
    if upper == "T":
        ctrl = _reflect(control, current)
        end = point(*args)
        out.append(Command("cubicBezTo", _elevate(current, ctrl, end)))
        return end, ctrl
    if upper == "A":
        end = point(args[5], args[6])
        for curve in _arc(
            current,
            end,
            rx=args[0],
            ry=args[1],
            rotation=args[2],
            large=bool(args[3]),
            sweep=bool(args[4]),
        ):
            out.append(Command("cubicBezTo", curve))
        return end, None
    out.append(Command("close"))
    return start, None


def _reflect(control, current):
    """The smooth control point: the previous one mirrored through the pen."""
    if control is None:
        return current
    return (2 * current[0] - control[0], 2 * current[1] - control[1])


def _elevate(p0, ctrl, p1):
    """A quadratic raised to the cubic DrawingML draws."""
    return (
        (p0[0] + 2 / 3 * (ctrl[0] - p0[0]), p0[1] + 2 / 3 * (ctrl[1] - p0[1])),
        (p1[0] + 2 / 3 * (ctrl[0] - p1[0]), p1[1] + 2 / 3 * (ctrl[1] - p1[1])),
        p1,
    )


def _arc(start, end, *, rx, ry, rotation, large, sweep):
    """An SVG endpoint arc as a list of cubic béziers, per the SVG implementation notes."""
    if start == end:
        return []
    rx, ry = abs(rx), abs(ry)
    if rx == 0 or ry == 0:
        return [(start, end, end)]  # degenerate: the spec says draw a line
    phi = math.radians(rotation)
    cos_phi, sin_phi = math.cos(phi), math.sin(phi)
    dx2, dy2 = (start[0] - end[0]) / 2, (start[1] - end[1]) / 2
    x1 = cos_phi * dx2 + sin_phi * dy2
    y1 = -sin_phi * dx2 + cos_phi * dy2

    # Radii too small to reach the endpoint are scaled up until they just do.
    lam = (x1 * x1) / (rx * rx) + (y1 * y1) / (ry * ry)
    if lam > 1:
        rx, ry = rx * math.sqrt(lam), ry * math.sqrt(lam)
    num = rx * rx * ry * ry - rx * rx * y1 * y1 - ry * ry * x1 * x1
    den = rx * rx * y1 * y1 + ry * ry * x1 * x1
    factor = math.sqrt(max(0.0, num / den)) * (-1 if large == sweep else 1)
    cx1, cy1 = factor * rx * y1 / ry, -factor * ry * x1 / rx
    cx = cos_phi * cx1 - sin_phi * cy1 + (start[0] + end[0]) / 2
    cy = sin_phi * cx1 + cos_phi * cy1 + (start[1] + end[1]) / 2

    theta = math.atan2((y1 - cy1) / ry, (x1 - cx1) / rx)
    delta = math.atan2((-y1 - cy1) / ry, (-x1 - cx1) / rx) - theta
    if not sweep and delta > 0:
        delta -= 2 * math.pi
    elif sweep and delta < 0:
        delta += 2 * math.pi

    segments = max(1, math.ceil(abs(delta) / _MAX_SWEEP))
    step = delta / segments
    # The magic constant that makes a cubic match a circular arc of this sweep.
    alpha = 4 / 3 * math.tan(step / 4)
    curves = []
    for seg in range(segments):
        a0 = theta + seg * step
        a1 = a0 + step
        p0 = _on_ellipse(cx, cy, rx, ry, cos_phi, sin_phi, a0)
        p1 = _on_ellipse(cx, cy, rx, ry, cos_phi, sin_phi, a1)
        d0 = _tangent(rx, ry, cos_phi, sin_phi, a0)
        d1 = _tangent(rx, ry, cos_phi, sin_phi, a1)
        curves.append(
            (
                (p0[0] + alpha * d0[0], p0[1] + alpha * d0[1]),
                (p1[0] - alpha * d1[0], p1[1] - alpha * d1[1]),
                p1,
            )
        )
    return curves


def _on_ellipse(cx, cy, rx, ry, cos_phi, sin_phi, angle):
    ex, ey = rx * math.cos(angle), ry * math.sin(angle)
    return (cx + cos_phi * ex - sin_phi * ey, cy + sin_phi * ex + cos_phi * ey)


def _tangent(rx, ry, cos_phi, sin_phi, angle):
    ex, ey = -rx * math.sin(angle), ry * math.cos(angle)
    return (cos_phi * ex - sin_phi * ey, sin_phi * ex + cos_phi * ey)


def to_drawingml(commands, *, view: tuple[float, float, float, float]) -> str:
    """The ``a:path`` body for ``commands``, scaled from ``view`` onto the unit grid.

    ``view`` is the SVG ``viewBox`` as ``(min_x, min_y, width, height)``. A non-square
    view is fitted and centred, so an icon keeps its drawn proportions in a square box.
    """
    min_x, min_y, width, height = view
    if width <= 0 or height <= 0:
        raise SpecError(f"svg viewBox needs a positive width and height, got {view}")
    scale = UNITS / max(width, height)
    pad_x = (UNITS - width * scale) / 2
    pad_y = (UNITS - height * scale) / 2

    def place(point):
        return (
            round((point[0] - min_x) * scale + pad_x),
            round((point[1] - min_y) * scale + pad_y),
        )

    out = []
    for command in commands:
        if command.tag == "close":
            out.append("<a:close/>")
            continue
        points = "".join(f'<a:pt x="{x}" y="{y}"/>' for x, y in map(place, command.points))
        out.append(f"<a:{command.tag}>{points}</a:{command.tag}>")
    return "".join(out)
