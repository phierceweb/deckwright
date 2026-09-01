"""Vendoring the Material Symbols set: fetch it, curate it, pack it, verify it.

Two committed files carry the set. ``glyphs.zip`` holds every SVG **stored rather than
deflated** — git and the wheel both compress it for us — sorted and epoch-stamped so
the same input is the same bytes. ``glyphs.sum`` is one ``<sha256>  <name>.svg`` line
per glyph with the upstream commit in its header: the review surface a re-vendor shows
up in, and what :func:`verify` checks the bundle against.
"""

from __future__ import annotations

from typing import Any

import hashlib
import math
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path


from pf_core.log import get_logger
from pf_core.utils.io import atomic_write_text

from deckwright.errors import RenderError, SpecError
from deckwright.icons.path import parse
from deckwright.utils.xml import fromstring as parse_xml

logger = get_logger(__name__)

MATERIAL = Path(__file__).parent / "glyphs" / "material"
BUNDLE = MATERIAL / "glyphs.zip"
MANIFEST = MATERIAL / "glyphs.sum"

UPSTREAM = "https://github.com/google/material-design-icons.git"
_SELECTION = "/symbols/web/*/materialsymbolsrounded/*_fill1_24px.svg"
_SUFFIX = "_fill1_24px"

_SVG = "{http://www.w3.org/2000/svg}"
_ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)
_PIN_RE = re.compile(r"^#\s*(?P<repo>\S+)\s*@\s*(?P<ref>[0-9a-f]{7,40})\s*$")

# Inserted into the legacy drawings that carry only width/height — the loader has no
# size to scale from otherwise. Every coordinate in those files falls inside 0..24.
_VIEWBOX = b'viewBox="0 0 24 24" '

SCANLINES = 400  # halve it and a real divergence falls between two scanlines unseen
# Fraction of the viewBox two coincident crossings may differ by and still be rounding.
NOISE = 1e-9


# --- the even-odd measure ----------------------------------------------------------


def contours(subpaths: tuple[str, ...]) -> list[list[tuple[float, float]]]:
    """Every closed contour of a glyph as a polyline, curves flattened."""
    out: list[list[tuple[float, float]]] = []
    run: list[tuple[float, float]] = []
    pen = (0.0, 0.0)
    for d in subpaths:
        for command in parse(d):
            if command.tag == "moveTo":
                if len(run) > 2:
                    out.append(run)
                pen = command.points[0]
                run = [pen]
            elif command.tag == "lnTo":
                pen = command.points[0]
                run.append(pen)
            elif command.tag == "cubicBezTo":
                c1, c2, end = command.points
                for step in range(1, 13):
                    t, u = step / 12, 1 - step / 12
                    run.append(
                        (
                            u**3 * pen[0]
                            + 3 * u * u * t * c1[0]
                            + 3 * u * t * t * c2[0]
                            + t**3 * end[0],
                            u**3 * pen[1]
                            + 3 * u * u * t * c1[1]
                            + 3 * u * t * t * c2[1]
                            + t**3 * end[1],
                        )
                    )
                pen = end
            else:
                if len(run) > 2:
                    out.append(run)
                pen = run[0] if run else pen
                run = [pen]
    if len(run) > 2:
        out.append(run)
    return out


def winding_disagreement(
    view: tuple[float, float, float, float], subpaths: tuple[str, ...]
) -> float:
    """Area the even-odd and nonzero fills differ over, in viewBox units.

    Exact in x: on one scanline the rules can only part company between consecutive
    crossings, so the disagreeing spans are summed rather than sampled.
    """
    min_y, height = view[1], view[3]
    step = height / SCANLINES
    rows: list[list[tuple[float, float, float, int]]] = [[] for _ in range(SCANLINES)]
    for contour in contours(subpaths):
        points = contour + [contour[0]]
        for (x1, y1), (x2, y2) in zip(points[:-1], points[1:], strict=True):
            if y1 == y2:
                continue
            lo, hi = sorted((y1, y2))
            first = max(0, math.ceil((lo - min_y) / step - 0.5))
            last = min(SCANLINES, math.ceil((hi - min_y) / step - 0.5))
            for row in range(first, last):
                rows[row].append((x1, y1, (x2 - x1) / (y2 - y1), 1 if y2 > y1 else -1))

    disagreed = 0.0
    for row, edges in enumerate(rows):
        if not edges:
            continue
        py = min_y + (row + 0.5) * step
        hits = sorted((x1 + (py - y1) * slope, direction) for x1, y1, slope, direction in edges)
        wind = 0
        for i in range(len(hits) - 1):
            wind += hits[i][1]
            if ((i + 1) % 2 == 1) != (wind != 0):
                disagreed += (hits[i + 1][0] - hits[i][0]) * step
    return disagreed


def needs_nonzero(svg: bytes) -> bool:
    """Whether this drawing only reads right under nonzero winding, so cannot ship.

    deckwright emits every subpath into one DrawingML ``a:path``, which is filled
    even-odd; the rules part company where contours overlap rather than nest.
    """
    root = parse_xml(svg)
    box = (root.get("viewBox") or "").split()
    if len(box) != 4:
        return False
    vx, vy, vw, vh = (float(v) for v in box)
    view = (vx, vy, vw, vh)
    subpaths = tuple(str(el.get("d")) for el in root.iter(f"{_SVG}path") if el.get("d"))
    if not subpaths:
        return False
    return winding_disagreement(view, subpaths) > NOISE * view[2] * view[3]


# --- fetch, curate, pack -----------------------------------------------------------


def fetch(ref: str, into: Path) -> Path:
    """Sparse-checkout just the glyph selection at ``ref``. Returns the checkout root.

    Blobless and depth-1, so the repository's full history never moves.

    Raises:
        RenderError: git is absent, or the fetch failed.
    """
    root = into / "material-design-icons"
    steps = (
        [
            "git",
            "clone",
            "--filter=blob:none",
            "--no-checkout",
            "--depth",
            "1",
            UPSTREAM,
            str(root),
        ],
        ["git", "-C", str(root), "sparse-checkout", "init", "--no-cone"],
        ["git", "-C", str(root), "sparse-checkout", "set", _SELECTION, "/LICENSE"],
        ["git", "-C", str(root), "fetch", "--depth", "1", "origin", ref],
        ["git", "-C", str(root), "checkout", ref],
    )
    for cmd in steps:
        try:
            subprocess.run(cmd, check=True, capture_output=True, encoding="utf-8", errors="replace")
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            raise RenderError(
                f"could not fetch the glyph upstream at {ref}",
                context={"step": cmd[:3], "stderr": getattr(e, "stderr", "")[-800:]},
                cause=e,
            )
    logger.info("glyphs_fetched", ref=ref, root=str(root))
    return root


def curate(checkout: Path) -> tuple[dict[str, bytes], list[str]]:
    """Upstream's files as ``{name.svg: bytes}``, plus the names dropped.

    The whole difference from upstream: the ``_fill1_24px`` suffix comes off the name,
    a missing ``viewBox`` is inserted, and a nonzero-winding drawing is left out.
    """
    kept: dict[str, bytes] = {}
    dropped: list[str] = []
    for svg in sorted(checkout.rglob(f"*{_SUFFIX}.svg")):
        name = svg.name.replace(_SUFFIX, "")
        data = svg.read_bytes()
        if b"viewBox" not in data:
            data = data.replace(b"<svg ", b"<svg " + _VIEWBOX, 1)
        if needs_nonzero(data):
            dropped.append(name)
            continue
        kept[name] = data
    logger.info(
        "glyphs_curated", upstream=len(kept) + len(dropped), kept=len(kept), dropped=len(dropped)
    )
    return kept, dropped


def pack(entries: dict[str, bytes], path: Path = BUNDLE) -> Path:
    """Write the bundle. Sorted, epoch-stamped and **stored** — see the module docstring."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as z:
        for name in sorted(entries):
            info = zipfile.ZipInfo(name, date_time=_ZIP_EPOCH)
            info.external_attr = 0o644 << 16
            info.create_system = 3
            info.compress_type = zipfile.ZIP_STORED
            z.writestr(info, entries[name])
    logger.info("glyphs_packed", bundle=str(path), glyphs=len(entries), bytes=path.stat().st_size)
    return path


def write_manifest(
    entries: dict[str, bytes], *, ref: str, dropped: int, path: Path = MANIFEST
) -> Path:
    """Write the pin and the per-glyph hashes as one file, so they cannot disagree."""
    lines = [
        f"# {UPSTREAM.removeprefix('https://github.com/').removesuffix('.git')} @ {ref}",
        f"# upstream {len(entries) + dropped}, kept {len(entries)}, "
        f"dropped {dropped} (need nonzero winding)",
    ]
    lines += [f"{hashlib.sha256(entries[name]).hexdigest()}  {name}" for name in sorted(entries)]
    atomic_write_text(path, "\n".join(lines) + "\n")
    return path


def read_manifest(path: Path = MANIFEST) -> tuple[str, dict[str, str]]:
    """The upstream ref and ``{name: sha256}``.

    Raises:
        SpecError: the manifest is missing or carries no pin.
    """
    if not path.is_file():
        raise SpecError(f"no glyph manifest at {path} — the checkout is incomplete")
    ref = ""
    hashes: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("#"):
            found = _PIN_RE.match(line)
            if found and not ref:
                ref = found.group("ref")
            continue
        if not line.strip():
            continue
        digest, _, name = line.partition("  ")
        hashes[name] = digest
    if not ref:
        raise SpecError(f"glyph manifest {path} names no upstream commit")
    return ref, hashes


def verify(bundle: Path = BUNDLE, manifest: Path = MANIFEST) -> list[str]:
    """Complaints about the bundle, empty when it matches the manifest exactly.

    Hashes are over each glyph's *uncompressed* bytes, never the bundle file: zip
    output depends on the zlib in use.
    """
    if not bundle.is_file():
        return [f"no glyph bundle at {bundle} — run 'deckwright glyphs sync'"]
    _, expected = read_manifest(manifest)
    problems: list[str] = []
    with zipfile.ZipFile(bundle) as z:
        present = set(z.namelist())
        missing = sorted(set(expected) - present)
        extra = sorted(present - set(expected))
        if missing:
            problems.append(
                f"{len(missing)} glyph(s) in the manifest are not in the "
                f"bundle: {', '.join(missing[:5])}"
            )
        if extra:
            problems.append(
                f"{len(extra)} glyph(s) in the bundle are not in the "
                f"manifest: {', '.join(extra[:5])}"
            )
        for name in sorted(set(expected) & present):
            if hashlib.sha256(z.read(name)).hexdigest() != expected[name]:
                problems.append(f"{name} does not match its manifest hash")
                if len(problems) > 10:
                    problems.append("…")
                    break
    if not (MATERIAL / "LICENSE").is_file():
        problems.append(f"the set's licence is missing from {MATERIAL}")
    return problems


def sync(
    ref: str | None = None, *, bundle: Path = BUNDLE, manifest: Path = MANIFEST
) -> dict[str, Any]:
    """Fetch, curate and write both files. Returns what changed.

    With no ``ref`` the manifest's own pin is used, reproducing the shipped set rather
    than moving it.
    """
    target = ref or read_manifest(manifest)[0]
    before = read_manifest(manifest)[1] if manifest.is_file() else {}
    with tempfile.TemporaryDirectory(prefix="deckwright-glyphs-") as tmp:
        checkout = fetch(target, Path(tmp))
        entries, dropped = curate(checkout)
        # A large tree of git objects: dropped before packing rather than held beside it.
        shutil.rmtree(checkout, ignore_errors=True)
        pack(entries, bundle)
        write_manifest(entries, ref=target, dropped=len(dropped), path=manifest)
    after = read_manifest(manifest)[1]
    return {
        "ref": target,
        "kept": len(entries),
        "dropped": len(dropped),
        "added": sorted(set(after) - set(before)),
        "removed": sorted(set(before) - set(after)),
        "changed": sorted(n for n in set(after) & set(before) if after[n] != before[n]),
    }
