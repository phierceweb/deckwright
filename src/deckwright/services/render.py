"""Render a ``.pptx`` to per-slide images via LibreOffice + Poppler.

The ``DECKWRIGHT_SOFFICE`` / ``DECKWRIGHT_PDFTOPPM`` / ``DECKWRIGHT_RENDER_DPI`` knobs are
listed in ``docs/cli.md``.
"""

from __future__ import annotations

import platform
import re
import subprocess
import tempfile
from pathlib import Path

from deckwright.errors import MissingToolError, RenderError
from deckwright.utils.env import env_str
from pf_core.log import get_logger
from pf_core.utils.env import resolve_int

logger = get_logger(__name__)

_SOFFICE_DEFAULT = "soffice"
_PDFTOPPM_DEFAULT = "pdftoppm"
_DPI_DEFAULT = 110

# Every external binary deckwright shells out to, so a runtime failure and `doctor`
# hand out the same install command.
INSTALL_HINTS = {
    "soffice": {
        "Darwin": "brew install --cask libreoffice",
        "Linux": "sudo apt-get install libreoffice-impress",
    },
    "pdftoppm": {"Darwin": "brew install poppler", "Linux": "sudo apt-get install poppler-utils"},
    "pdftotext": {"Darwin": "brew install poppler", "Linux": "sudo apt-get install poppler-utils"},
    "fc-list": {"Darwin": "brew install fontconfig", "Linux": "sudo apt-get install fontconfig"},
    "chrome": {
        "Darwin": "brew install --cask google-chrome",
        "Linux": "sudo apt-get install chromium",
    },
}
# What pdftoppm itself writes: slide-<page>.<image ext>. The sweep below is scoped to
# these, because --outdir is a free-form user path that may hold anything else.
_PAGE_SUFFIXES = frozenset({".jpg", ".jpeg", ".png", ".ppm", ".pgm", ".pbm", ".tif", ".tiff"})


def install_hint(tool: str) -> str:
    """The command that installs ``tool`` on this platform."""
    return INSTALL_HINTS.get(tool, {}).get(platform.system(), f"install {tool}")


def _missing_binary(tool: str, binary: str, *, env_var: str, needed_by: str) -> MissingToolError:
    return MissingToolError(
        f"{tool} not found ({binary}) — needed by {needed_by}; {install_hint(tool)}, "
        f"or set {env_var} to the path of an installed one"
    )


def _rendered_pages(outdir: Path) -> list[Path]:
    """The page images a previous run of this function left in ``outdir``.

    Matched on the whole stem, not a prefix: callers delete everything this returns,
    and ``slide-3-final.png`` is a file someone named.
    """
    return sorted(
        p
        for p in outdir.glob("slide-[0-9]*")
        if p.is_file() and p.suffix.lower() in _PAGE_SUFFIXES and re.fullmatch(r"slide-\d+", p.stem)
    )


def render_to_images(
    pptx_path,
    outdir,
    *,
    dpi: int | None = None,
    soffice: str | None = None,
    pdftoppm: str | None = None,
    fmt: str = "jpeg",
) -> list[str]:
    """Render ``pptx_path`` to ``outdir/slide-NN.<ext>`` and return the image paths, sorted.

    Args:
        pptx_path: Path to the source ``.pptx``.
        outdir: Directory for the intermediate PDF and slide images (created if missing).
        dpi: Rasterization DPI. Falls back to ``$DECKWRIGHT_RENDER_DPI`` then 110.
        soffice: soffice command. Falls back to ``$DECKWRIGHT_SOFFICE`` then ``"soffice"``.
        pdftoppm: pdftoppm command. Falls back to ``$DECKWRIGHT_PDFTOPPM`` then
            ``"pdftoppm"``.
        fmt: pdftoppm image format — ``"jpeg"`` or ``"png"``.

    Returns:
        Sorted list of generated image paths.

    Raises:
        RenderError: a binary is missing, or the conversion or rasterization failed.
    """
    # soffice runs in its own profile dir, so a relative path on either side would
    # resolve there rather than where the caller meant.
    pptx_path = Path(pptx_path).resolve()
    outdir = Path(outdir).resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    dpi = resolve_int(dpi, "DECKWRIGHT_RENDER_DPI", default=_DPI_DEFAULT)
    soffice = env_str(soffice, "DECKWRIGHT_SOFFICE", default=_SOFFICE_DEFAULT)
    pdftoppm = env_str(pdftoppm, "DECKWRIGHT_PDFTOPPM", default=_PDFTOPPM_DEFAULT)

    pdf = outdir / f"{pptx_path.stem}.pdf"
    # LibreOffice exits 0 without converting when another process holds its profile.
    # With the previous run's PDF still here that failure is invisible: the pages are
    # re-rasterised from it and reported as this deck's.
    pdf.unlink(missing_ok=True)

    if not pptx_path.is_file():
        raise RenderError(
            f"no deck to render at {pptx_path}",
            context={"pptx": str(pptx_path)},
        )

    logger.info("render_pptx_start", pptx=str(pptx_path), outdir=str(outdir), dpi=dpi)
    # LibreOffice locks one shared user profile, so a concurrent conversion exits
    # without converting and without a usable error. A profile per process fixes it.
    with tempfile.TemporaryDirectory(prefix="deckwright-soffice-") as profile:
        try:
            subprocess.run(
                [
                    soffice,
                    f"-env:UserInstallation=file://{profile}",
                    "--headless",
                    "--convert-to",
                    "pdf",
                    "--outdir",
                    str(outdir),
                    str(pptx_path),
                ],
                check=True,
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                # LibreOffice writes a `render/share` tree into whatever directory it
                # is started in, so it is started in the profile it already owns.
                cwd=profile,
            )
        except FileNotFoundError as e:
            raise _missing_binary(
                "soffice",
                soffice,
                env_var="DECKWRIGHT_SOFFICE",
                needed_by="render, and QA's render-based checks",
            ) from e
        except subprocess.CalledProcessError as e:
            raise RenderError(
                "LibreOffice PDF conversion failed",
                context={"pptx": str(pptx_path), "soffice": soffice},
                cause=e,
            )

    if not pdf.exists():
        raise RenderError(
            f"LibreOffice reported success but wrote no PDF. Two things cause this: an "
            f"input path it could not read ({pptx_path}), or a leftover soffice process "
            f"holding the profile this run needed — check with 'pgrep -fl soffice'",
            context={"pdf": str(pdf), "pptx": str(pptx_path), "soffice": soffice},
        )

    for stale in _rendered_pages(outdir):
        stale.unlink()
    flag = "-jpeg" if fmt == "jpeg" else f"-{fmt}"
    try:
        subprocess.run(
            [pdftoppm, flag, "-r", str(dpi), str(pdf), str(outdir / "slide")],
            check=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError as e:
        raise _missing_binary(
            "pdftoppm",
            pdftoppm,
            env_var="DECKWRIGHT_PDFTOPPM",
            needed_by="render, and QA's render-based checks",
        ) from e
    except subprocess.CalledProcessError as e:
        raise RenderError(
            "pdftoppm rasterization failed",
            context={"pdf": str(pdf), "pdftoppm": pdftoppm},
            cause=e,
        )

    images = [str(p) for p in _rendered_pages(outdir)]
    logger.info("render_pptx_done", count=len(images))
    return images
