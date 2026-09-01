"""deckwright exception hierarchy.

``FlowException`` subclasses carry no context dict, so callers embed the slide index and
field path in the message itself.
"""

from __future__ import annotations

from pf_core.exceptions import ClientError, ConfigurationError, InvalidInputError


class SpecError(InvalidInputError):
    """A deck spec, or a built deck handed back to the tool, is malformed."""


class ThemeError(ConfigurationError):
    """A theme file, or the template it references, is missing or malformed."""


class LayoutError(InvalidInputError):
    """A layout or body component is unknown, is registered twice, or was handed
    content it cannot place."""


class MissingToolError(ConfigurationError):
    """An external tool the command needs is not installed, or is not where a
    ``DECKWRIGHT_*`` variable says it is."""


class RenderError(ClientError):
    """An external renderer (headless Chrome, LibreOffice) ran and failed."""
