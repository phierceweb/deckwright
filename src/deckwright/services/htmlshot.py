"""Rasterize an HTML string to a PNG with headless Chrome.

The ``DECKWRIGHT_CHROME`` / ``DECKWRIGHT_SHOT_*`` knobs are listed in ``docs/cli.md``.
"""

from __future__ import annotations

import base64
import hashlib
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from PIL import Image, ImageChops
from pptx.util import Inches

from pf_core.exceptions import ConfigurationError
from pf_core.log import get_logger
from pf_core.utils.env import resolve_bool, resolve_int

from deckwright.errors import MissingToolError, RenderError
from deckwright.services.render import install_hint
from deckwright.utils.a11y import describe
from deckwright.utils.env import env_str

logger = get_logger(__name__)

_SCALE_DEFAULT = 2
_CANVAS_H_DEFAULT = 4000  # tall render canvas; the card is autocropped out of the whitespace
_CANVAS_H_ENV_VAR = "DECKWRIGHT_SHOT_CANVAS_H"
_TIMEOUT_S_DEFAULT = 60
_NO_SANDBOX_ENV_VAR = "DECKWRIGHT_CHROME_NO_SANDBOX"
# Chrome refuses to sandbox itself as root, and some hardened kernels deny the
# unprivileged user namespace it needs. Both say so on stderr.
_SANDBOX_TELL = re.compile(
    r"no usable sandbox|--no-sandbox|sandbox.{0,40}(?:fail|denied)", re.I | re.S
)
# How far a channel must sit from white to count as ink.
_INK_THRESHOLD = 8

# Chrome crops at the window height with no error, so the laid-out document height is
# published into an attribute and read back out of ``--dump-dom``.
_HEIGHT_ATTR = "data-deckwright-doc-h"
_HEIGHT_JS = (
    "(function(){var m=function(){document.documentElement.setAttribute("
    f"'{_HEIGHT_ATTR}',String(document.documentElement.scrollHeight));}};"
    "m();addEventListener('load',m);})();"
)
_HEIGHT_PROBE = f"<script>{_HEIGHT_JS}</script>"
_HEIGHT_RE = re.compile(rf'{_HEIGHT_ATTR}="(\d+)"')

# A card is a file:// document, so a file:// frame in it resolves and renders a local
# file into the PNG. SECURITY.md carries the model.
_PROBE_HASH = base64.b64encode(hashlib.sha256(_HEIGHT_JS.encode("utf-8")).digest()).decode()
CSP_META = (
    '<meta http-equiv="Content-Security-Policy" content="'
    "default-src 'none'; "
    "img-src data: https: http:; "
    "font-src data: https: http:; "
    "style-src 'unsafe-inline'; "
    f"script-src 'sha256-{_PROBE_HASH}'"
    '">'
)
_HEAD_RE = re.compile(r"<head[^>]*>", re.I)


def _with_csp(html: str) -> str:
    """Return ``html`` with the policy first in ``<head>`` — it must precede what it governs."""
    match = _HEAD_RE.search(html)
    if match:
        return html[: match.end()] + CSP_META + html[match.end() :]
    return CSP_META + html


# Probed in order when DECKWRIGHT_CHROME is unset. Bare names go through PATH; the
# rest are the macOS app-bundle binaries.
_CHROME_CANDIDATES = (
    "google-chrome",
    "google-chrome-stable",
    "chromium",
    "chromium-browser",
    "chrome",
    "chrome-headless-shell",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
)


def _resolve_chrome(chrome: str | None) -> str:
    """Return an explicit/env browser path, else the first candidate that exists."""
    resolved = env_str(chrome, "DECKWRIGHT_CHROME", default="").strip()
    if resolved:
        return resolved
    for cand in _CHROME_CANDIDATES:
        if "/" in cand:
            if os.path.exists(cand):
                return cand
        elif shutil.which(cand):
            return cand
    raise MissingToolError(
        f"no Chrome/Chromium binary found — needed by shot and any 'document:' slide; "
        f"{install_hint('chrome')}, or set DECKWRIGHT_CHROME to the path of an installed one"
    )


def _no_sandbox() -> bool:
    """Whether to hand Chrome ``--no-sandbox``.

    A card's HTML can carry script, so the sandbox is a real boundary and stays on by
    default. Running as root it cannot work at all, and there the flag is the only way
    the browser starts.
    """
    if resolve_bool(None, _NO_SANDBOX_ENV_VAR, default=False):
        return True
    geteuid = getattr(os, "geteuid", None)
    return geteuid is not None and geteuid() == 0


def _sandbox_advice(stderr_tail: str) -> str:
    """A pointer to the escape hatch, when the browser died for want of a sandbox."""
    if not _SANDBOX_TELL.search(stderr_tail):
        return ""
    return (
        f" — the browser could not start its sandbox. Set {_NO_SANDBOX_ENV_VAR}=1 to "
        f"run it unsandboxed, which is safe only where the rendered HTML is as "
        f"trusted as a script you would run"
    )


def _chrome_cmd(
    chrome: str,
    file_url: str,
    out_path: str,
    *,
    width: int,
    height: int,
    scale: int,
    user_data_dir: str,
) -> list[str]:
    """Build the headless-Chrome screenshot argv. ``--dump-dom`` writes the laid-out
    DOM (carrying the height probe) to stdout in the same run as the screenshot."""
    return [
        chrome,
        "--headless=new",
        "--disable-gpu",
        *(["--no-sandbox"] if _no_sandbox() else []),
        "--no-first-run",
        "--no-default-browser-check",
        # Stop full Chrome from waking GoogleUpdater / crashpad / GCM on launch.
        "--disable-background-networking",
        "--disable-component-update",
        "--disable-breakpad",
        "--disable-sync",
        "--no-pings",
        "--hide-scrollbars",
        "--disable-extensions",
        "--disable-dev-shm-usage",
        f"--user-data-dir={user_data_dir}",
        f"--force-device-scale-factor={scale}",
        f"--window-size={width},{height}",
        f"--screenshot={out_path}",
        "--dump-dom",
        file_url,
    ]


def _probe_height(dom: str) -> int | None:
    """Document height (CSS px) the probe published, or None if it never ran."""
    match = _HEIGHT_RE.search(dom)
    return int(match.group(1)) if match else None


def _edge_rows_inked(png: Path) -> tuple[bool, bool]:
    """Whether the render's first and last pixel rows carry ink."""
    with Image.open(png) as img:
        rgb = img.convert("RGB")
        diff = ImageChops.difference(rgb, Image.new("RGB", rgb.size, (255, 255, 255)))
        mask = diff.convert("L").point(lambda p: 255 if p > _INK_THRESHOLD else 0)
    width, height = mask.size
    return (
        bool(mask.crop((0, 0, width, 1)).getbbox()),
        bool(mask.crop((0, height - 1, width, height)).getbbox()),
    )


def _check_not_clipped(dom: str, *, canvas_height: int, out_path: Path) -> None:
    """Raise if the document was taller than the canvas Chrome rendered it in.

    Content that swallows the rest of the parse leaves no probe height to read, and
    the pixels are then the only evidence: a card floats on white, so ink on the last
    row and none on the first means the canvas cut it off.
    """
    doc_h = _probe_height(dom)
    if doc_h is None:
        top_inked, bottom_inked = _edge_rows_inked(out_path)
        if bottom_inked and not top_inked:
            raise RenderError(
                f"the height probe did not run and the content reaches the last row "
                f"of the {canvas_height}px render canvas, so the browser clipped it "
                f"— raise {_CANVAS_H_ENV_VAR} or shorten the source",
                context={"canvas_height_px": canvas_height, "out": str(out_path)},
            )
        logger.warning("html_shot_height_unknown", out=str(out_path), canvas_height=canvas_height)
        return
    if doc_h > canvas_height:
        raise RenderError(
            f"content is {doc_h}px tall but the render canvas is only {canvas_height}px — "
            f"the browser clipped it; raise {_CANVAS_H_ENV_VAR} to at least {doc_h} "
            f"or shorten the source",
            context={
                "doc_height_px": doc_h,
                "canvas_height_px": canvas_height,
                "out": str(out_path),
            },
        )


def _autocrop(img: Image.Image, *, threshold: int = _INK_THRESHOLD, pad: int = 0) -> Image.Image:
    """Crop ``img`` to the bounding box of everything that differs from white."""
    rgb = img.convert("RGB")
    diff = ImageChops.difference(rgb, Image.new("RGB", rgb.size, (255, 255, 255)))
    mask = diff.convert("L").point(lambda p: 255 if p > threshold else 0)
    bbox = mask.getbbox()
    if not bbox:
        return img
    if pad:
        left, top, right, bottom = bbox
        bbox = (
            max(left - pad, 0),
            max(top - pad, 0),
            min(right + pad, img.width),
            min(bottom + pad, img.height),
        )
    return img.crop(bbox)


def _tail(path: Path, n: int = 1500) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")[-n:]
    except OSError:
        return ""


def _terminate(proc: subprocess.Popen) -> None:
    """SIGTERM the browser (SIGKILL if it ignores us); reparented daemons are left alone."""
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


def _await_screenshot(
    proc: subprocess.Popen,
    out_path: Path,
    err_log: Path,
    timeout_s: int,
    *,
    poll: float = 0.3,
    stable_for: float = 0.6,
) -> None:
    """Block until ``out_path`` appears and its size settles (write finished), then return."""
    deadline = time.monotonic() + timeout_s
    stable_since = None
    last_size = -1
    while time.monotonic() < deadline:
        size = out_path.stat().st_size if out_path.exists() else -1
        if size > 0 and size == last_size:
            if stable_since is None:
                stable_since = time.monotonic()
            if time.monotonic() - stable_since >= stable_for:
                return
        else:
            stable_since = None
        last_size = size
        if proc.poll() is not None and size <= 0:
            tail = _tail(err_log)
            raise RenderError(
                "Chrome exited without a screenshot" + _sandbox_advice(tail),
                context={"stderr_tail": tail},
            )
        time.sleep(poll)
    tail = _tail(err_log)
    raise RenderError(
        "headless Chrome timed out" + _sandbox_advice(tail),
        context={"timeout_s": timeout_s, "stderr_tail": tail},
    )


def render_html_to_png(
    html: str,
    out_path,
    *,
    width: int = 1000,
    scale: int | None = None,
    chrome: str | None = None,
    canvas_height: int | None = None,
    autocrop: bool = True,
    pad: int = 20,
    timeout: int | None = None,
) -> str:
    """Render an HTML document to a PNG via headless Chrome, cropped to content.

    Args:
        html: HTML source (e.g. from :func:`deckwright.services.htmlcard.window_card`).
        out_path: Destination ``.png`` (parent dirs are created).
        width: Layout width in CSS px — match the card's ``max_width``.
        scale: Device scale factor. Falls back to ``$DECKWRIGHT_SHOT_SCALE`` then 2.
        chrome: Browser command/path. Falls back to ``$DECKWRIGHT_CHROME`` then autodetect.
        canvas_height: Render canvas in CSS px; the card is cropped out of the
            whitespace. Falls back to ``$DECKWRIGHT_SHOT_CANVAS_H`` then 4000.
        autocrop: Trim the surrounding whitespace to the card's bounding box.
        pad: Whitespace margin (px) kept around the crop.
        timeout: Seconds before the browser is killed. Falls back to
            ``$DECKWRIGHT_SHOT_TIMEOUT_S`` then 60.

    Returns:
        ``str(out_path)``.

    Raises:
        ConfigurationError: the canvas is not positive.
        MissingToolError: no browser binary was found, or the configured one does not
            exist.
        RenderError: the invocation failed, timed out, or produced no image; or the
            document was taller than the canvas, so the browser clipped it.
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.unlink(missing_ok=True)
    scale = resolve_int(scale, "DECKWRIGHT_SHOT_SCALE", default=_SCALE_DEFAULT)
    timeout_s = resolve_int(timeout, "DECKWRIGHT_SHOT_TIMEOUT_S", default=_TIMEOUT_S_DEFAULT)
    canvas_h = resolve_int(canvas_height, _CANVAS_H_ENV_VAR, default=_CANVAS_H_DEFAULT)
    if canvas_h <= 0:
        raise ConfigurationError(
            f"{_CANVAS_H_ENV_VAR} must be a positive number of CSS px, got {canvas_h}"
        )
    chrome_bin = _resolve_chrome(chrome)

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        src = Path(td) / "card.html"
        src.write_text(_with_csp(html) + _HEIGHT_PROBE, encoding="utf-8")
        err_log = Path(td) / "chrome.stderr"
        dom_log = Path(td) / "chrome.dom"
        cmd = _chrome_cmd(
            chrome_bin,
            src.as_uri(),
            str(out_path),
            width=width,
            height=canvas_h,
            scale=scale,
            user_data_dir=str(Path(td) / "profile"),
        )
        logger.info(
            "html_shot_start", chrome=chrome_bin, width=width, scale=scale, out=str(out_path)
        )
        # Full Chrome lingers on its updater/crashpad children long after writing the
        # PNG: wait for the file to settle, then kill it. Output goes to files, never a
        # PIPE those children would hold open.
        with open(err_log, "wb") as errf, open(dom_log, "wb") as domf:
            try:
                proc = subprocess.Popen(cmd, stdout=domf, stderr=errf)
            except OSError as e:
                raise MissingToolError(
                    f"could not start the browser at {chrome_bin!r} — "
                    f"{install_hint('chrome')}, or set DECKWRIGHT_CHROME to the path of "
                    f"an installed one"
                ) from e
            try:
                _await_screenshot(proc, out_path, err_log, timeout_s)
            finally:
                _terminate(proc)
        dom = dom_log.read_text(encoding="utf-8", errors="replace")

    if not out_path.exists() or out_path.stat().st_size == 0:
        raise RenderError("Chrome produced no screenshot", context={"out": str(out_path)})
    _check_not_clipped(dom, canvas_height=canvas_h, out_path=out_path)

    if autocrop:
        _autocrop(Image.open(out_path), pad=pad).save(out_path)
    logger.info("html_shot_done", out=str(out_path))
    return str(out_path)


def card_to_slide(
    slide,
    html: str,
    *,
    left: float,
    top: float,
    width: float | None = None,
    height: float | None = None,
    render_width: int = 1000,
    scale: int | None = None,
    chrome: str | None = None,
    png_path=None,
):
    """Render an HTML card to PNG and place it on ``slide`` as a picture.

    Positions the picture at (``left``, ``top``) inches; pass exactly one of
    ``width`` / ``height`` (inches) to scale while preserving aspect ratio.

    Args:
        slide: Target python-pptx slide.
        html: HTML source (typically from :mod:`deckwright.services.htmlcard`).
        left: Picture left edge, inches.
        top: Picture top edge, inches.
        width: Picture width, inches (omit to derive from ``height``).
        height: Picture height, inches (omit to derive from ``width``).
        render_width: HTML layout width in CSS px passed to the renderer.
        scale: Device scale factor (see :func:`render_html_to_png`).
        chrome: Browser command/path (see :func:`render_html_to_png`).
        png_path: Where to keep the intermediate PNG; a temp file if omitted.

    Returns:
        The added picture shape.
    """
    if png_path is None:
        fd, png_path = tempfile.mkstemp(suffix=".png")
        os.close(fd)
    render_html_to_png(html, png_path, width=render_width, scale=scale, chrome=chrome)
    picture = slide.shapes.add_picture(
        png_path,
        Inches(left),
        Inches(top),
        width=Inches(width) if width is not None else None,
        height=Inches(height) if height is not None else None,
    )
    describe(picture)
    return picture
