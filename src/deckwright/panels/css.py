"""Expose a theme to a panel's stylesheet as CSS custom properties.

Anything handing a font name to a browser must go through :func:`font_stack` /
:func:`mono_stack`, never write a bare face name into markup: a brand face is rarely
installed on the rendering machine, and with no generic fallback the browser silently
substitutes its own default.
"""

from __future__ import annotations

from deckwright.theme.model import Theme

# A var() fallback only applies when the variable is undefined, so the generic
# fallback has to live inside the custom property's own value.
_SANS_FALLBACK = '-apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif'
_MONO_FALLBACK = 'ui-monospace, "SF Mono", Menlo, monospace'


def font_stack(theme: Theme) -> str:
    """The theme's display face as a CSS font-family list ending in a generic fallback."""
    return f'"{theme.face}", {_SANS_FALLBACK}'


def mono_stack(theme: Theme) -> str:
    """The theme's monospace face as a CSS font-family list ending in a generic fallback."""
    return f'"{theme.mono}", {_MONO_FALLBACK}'


def panel_css(theme: Theme) -> str:
    """Return a ``:root`` block declaring the theme's colours, type ramp and faces."""
    lines = [":root {"]
    lines += [f"  --c-{role}: #{value};" for role, value in sorted(theme.palette.roles.items())]
    lines += [f"  --t-{role}: {style.size}pt;" for role, style in sorted(theme.ramp.items())]
    lines += [f"  --font: {font_stack(theme)};", f"  --font-mono: {mono_stack(theme)};", "}"]
    return "\n".join(lines)
