"""Find, start, wait on and stop a headless Chrome. Nothing here knows what it renders."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
from pathlib import Path

from pf_core.utils.env import resolve_bool

from deckwright.errors import MissingToolError, RenderError
from deckwright.services.render import install_hint
from deckwright.utils.env import env_str

NO_SANDBOX_ENV_VAR = "DECKWRIGHT_CHROME_NO_SANDBOX"
# Chrome refuses to sandbox itself as root, and some hardened kernels deny the
# unprivileged user namespace it needs. Both say so on stderr.
_SANDBOX_TELL = re.compile(
    r"no usable sandbox|--no-sandbox|sandbox.{0,40}(?:fail|denied)", re.I | re.S
)

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


def resolve_chrome(chrome: str | None) -> str:
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


def no_sandbox() -> bool:
    """Whether to hand Chrome ``--no-sandbox``.

    A card's HTML can carry script, so the sandbox is a real boundary and stays on by
    default. Running as root it cannot work at all, and there the flag is the only way
    the browser starts.
    """
    if resolve_bool(None, NO_SANDBOX_ENV_VAR, default=False):
        return True
    geteuid = getattr(os, "geteuid", None)
    return geteuid is not None and geteuid() == 0


def sandbox_advice(stderr_tail: str) -> str:
    """A pointer to the escape hatch, when the browser died for want of a sandbox."""
    if not _SANDBOX_TELL.search(stderr_tail):
        return ""
    return (
        f" — the browser could not start its sandbox. Set {NO_SANDBOX_ENV_VAR}=1 to "
        f"run it unsandboxed, which is safe only where the rendered HTML is as "
        f"trusted as a script you would run"
    )


def chrome_cmd(
    chrome: str,
    file_url: str,
    out_path: str,
    *,
    width: int,
    height: int,
    scale: int,
    user_data_dir: str,
    transparent: bool = False,
) -> list[str]:
    """Build the headless-Chrome screenshot argv. ``--dump-dom`` writes the laid-out
    DOM (carrying the height probe) to stdout in the same run as the screenshot."""
    return [
        chrome,
        "--headless=new",
        "--disable-gpu",
        *(["--no-sandbox"] if no_sandbox() else []),
        "--no-first-run",
        "--no-default-browser-check",
        # Stop full Chrome from waking GoogleUpdater / crashpad / GCM on launch.
        "--disable-background-networking",
        "--disable-component-update",
        "--disable-breakpad",
        "--disable-sync",
        "--no-pings",
        "--hide-scrollbars",
        *(["--default-background-color=00000000"] if transparent else []),
        "--disable-extensions",
        "--disable-dev-shm-usage",
        f"--user-data-dir={user_data_dir}",
        f"--force-device-scale-factor={scale}",
        f"--window-size={width},{height}",
        f"--screenshot={out_path}",
        "--dump-dom",
        file_url,
    ]


def log_tail(path: Path, n: int = 1500) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")[-n:]
    except OSError:
        return ""


def terminate(proc: subprocess.Popen) -> None:
    """SIGTERM the browser (SIGKILL if it ignores us); reparented daemons are left alone."""
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


def await_screenshot(
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
            tail = log_tail(err_log)
            raise RenderError(
                "Chrome exited without a screenshot" + sandbox_advice(tail),
                context={"stderr_tail": tail},
            )
        time.sleep(poll)
    tail = log_tail(err_log)
    raise RenderError(
        "headless Chrome timed out" + sandbox_advice(tail),
        context={"timeout_s": timeout_s, "stderr_tail": tail},
    )
