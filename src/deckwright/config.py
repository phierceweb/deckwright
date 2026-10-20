"""deckwright configuration.

Subclass ``pw_foundation.config.AppConfig`` and add project settings as class
attributes (env var name == attribute name). See pw-foundation ``docs/config.md``.
"""

from __future__ import annotations

from pathlib import Path

from pw_foundation.config import AppConfig


class Config(AppConfig):
    """Project settings."""


def load_env() -> Config:
    """Load ``.env`` from the working directory into the process environment.

    Entry points call this on startup: every ``DECKWRIGHT_*`` knob is resolved from
    ``os.environ`` at call time, so an unloaded ``.env`` leaves them all inert.
    """
    env = Path(".env")
    return Config(env_file=env if env.exists() else None)


cfg = load_env()
