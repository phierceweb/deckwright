"""Extract the text a rendered deck actually contains, and diff it against intent.

Config (env, read at call time, so ``.env`` changes take effect between runs):

- ``DECKWRIGHT_PDFTOTEXT``           — the pdftotext command (default ``pdftotext``).
- ``DECKWRIGHT_PDFTOTEXT_TIMEOUT_S`` — seconds before it is killed (default 60).
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from pf_core.log import get_logger, log_exception
from pf_core.utils.env import resolve_int

from deckwright.errors import RenderError
from deckwright.compile.record import box_of
from deckwright.qa.model import Finding, Severity
from deckwright.utils.env import env_str

logger = get_logger(__name__)

_PDFTOTEXT_DEFAULT = "pdftotext"
_TIMEOUT_S_DEFAULT = 60
_PT_PER_IN = 72.0
# The renderer may set a glyph a hair past the box the shape was measured for.
_CROP_PAD_PT = 4


def _run_pdftotext(argv: list[str], pdf_path: Path, timeout_s: int) -> str:
    """pdftotext's stdout, decoded as UTF-8 whatever the platform locale is."""
    try:
        result = subprocess.run(
            argv,
            capture_output=True,
            check=True,
            timeout=timeout_s,
            encoding="utf-8",
            errors="replace",
        )
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as e:
        raise RenderError(f"pdftotext failed on {pdf_path}", cause=e) from e
    return str(result.stdout)


def extract_pages(
    pdf_path: str | Path,
    *,
    layout: bool = False,
    pdftotext: str | None = None,
    timeout: int | None = None,
) -> list[str]:
    """Return the text of each page of ``pdf_path``, in order.

    Both extraction modes are returned because each splits lines the other keeps whole:
    reading order on wide tracking, ``-layout`` on whatever sits beside a wrapped line.

    Raises:
        RenderError: the PDF is missing, or pdftotext failed or timed out.
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.is_file():
        raise RenderError(f"PDF not found: {pdf_path}")
    binary = env_str(pdftotext, "DECKWRIGHT_PDFTOTEXT", default=_PDFTOTEXT_DEFAULT)
    timeout_s = resolve_int(timeout, "DECKWRIGHT_PDFTOTEXT_TIMEOUT_S", default=_TIMEOUT_S_DEFAULT)
    argv = [binary, *(["-layout"] if layout else []), str(pdf_path), "-"]
    pages = _run_pdftotext(argv, pdf_path, timeout_s).split("\f")
    if pages and not pages[-1].strip():
        pages.pop()
    logger.info("pdf_text_extracted", pdf=str(pdf_path), pages=len(pages))
    return pages


def crop_text(
    pdf_path: str | Path,
    page: int,
    box: tuple[float, float, float, float],
    *,
    pdftotext: str | None = None,
    timeout: int | None = None,
) -> str:
    """The text inside *box* — inches from the slide's top left — on 1-based *page*.

    Raises:
        RenderError: pdftotext failed or timed out.
    """
    left, top, width, height = box
    binary = env_str(pdftotext, "DECKWRIGHT_PDFTOTEXT", default=_PDFTOTEXT_DEFAULT)
    timeout_s = resolve_int(timeout, "DECKWRIGHT_PDFTOTEXT_TIMEOUT_S", default=_TIMEOUT_S_DEFAULT)
    argv = [
        binary,
        "-f",
        str(page),
        "-l",
        str(page),
        "-x",
        str(max(0, int(left * _PT_PER_IN) - _CROP_PAD_PT)),
        "-y",
        str(max(0, int(top * _PT_PER_IN) - _CROP_PAD_PT)),
        "-W",
        str(int(width * _PT_PER_IN) + 2 * _CROP_PAD_PT),
        "-H",
        str(int(height * _PT_PER_IN) + 2 * _CROP_PAD_PT),
        str(pdf_path),
        "-",
    ]
    return _run_pdftotext(argv, Path(pdf_path), timeout_s)


def normalise(text: str) -> str:
    """Collapse whitespace and casefold, so layout differences do not read as loss."""
    return " ".join(text.split()).casefold()


def _matchable(text: str) -> str:
    """Fold *text* for containment: normalised, then spacing and hyphens dropped.

    pdftotext rebuilds a line the renderer wrapped at a hyphen two ways — reading
    order deletes the hyphen ("non-text" -> "nontext"), -layout keeps it with the
    row break beside it ("non- text"). Ignoring spacing and hyphens erases both.
    """
    return normalise(text).replace(" ", "").replace("-", "")


def _own_box_holds(
    pdf_path: str | Path,
    page: int,
    box: tuple[float, float, float, float],
    needle: str,
    cache: dict[tuple[int, tuple[float, float, float, float]], str],
) -> bool:
    """Whether *needle* is in the shape's own frame, cropped out of the page.

    pdftotext merges side-by-side placements row by row, so one shape's wrapped line
    arrives with a neighbour's spliced into it and no longer reads contiguously.
    """
    key = (page, box)
    if key not in cache:
        try:
            cache[key] = _matchable(crop_text(pdf_path, page, box))
        except RenderError as e:
            log_exception(e, message_prepend="overflow crop failed", log_level="warning")
            cache[key] = ""
    return bool(cache[key]) and needle in cache[key]


def check_overflow(
    manifest: dict[str, Any],
    pages: list[str],
    alt_pages: list[str] | None = None,
    *,
    pdf_path: str | Path | None = None,
) -> list[Finding]:
    """Flag recorded text that did not survive into the rendered page.

    Text is missing only if absent from *both* extractions (see :func:`extract_pages`).
    ``rendered="image"`` records are skipped: a PDF extractor cannot see text in a picture.
    Given *pdf_path*, a line the whole page does not hold is asked for again inside the
    shape's own box, which is what a multi-column slide needs.
    """
    slides = manifest.get("slides", [])
    if len(slides) != len(pages):
        return [
            Finding(
                slide=0,
                check="page-count",
                severity=Severity.ERROR,
                detail=f"manifest has {len(slides)} slide(s) but the render has {len(pages)} page(s)",
            )
        ]

    alt = alt_pages if alt_pages and len(alt_pages) == len(pages) else [""] * len(pages)
    findings: list[Finding] = []
    cropped: dict[tuple[int, tuple[float, float, float, float]], str] = {}
    for page_no, (slide, page, alt_page) in enumerate(zip(slides, pages, alt, strict=True), 1):
        haystack = _matchable(page)
        alt_haystack = _matchable(alt_page)
        for shape in slide.get("shapes", []):
            if shape.get("rendered", "native") != "native":
                continue
            lines = shape.get("lines") or ([shape["text"]] if shape.get("text") else [])
            for line in lines:
                needle = _matchable(str(line))
                if not needle or needle in haystack or needle in alt_haystack:
                    continue
                box = box_of(shape)
                if (
                    pdf_path is not None
                    and box
                    and _own_box_holds(pdf_path, page_no, box, needle, cropped)
                ):
                    continue
                findings.append(
                    Finding(
                        slide=slide["index"],
                        check="overflow",
                        severity=Severity.ERROR,
                        detail=f"{str(line)[:70]!r} was not found in the rendered slide",
                        box=box,
                        shape=shape.get("name"),
                    )
                )
    return findings
