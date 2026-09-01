"""Render markdown or arbitrary HTML into a styled "app window" card.

A macOS-style window frame — traffic-light titlebar, rounded card, soft drop shadow —
around the doc and code snippets that get screenshotted into slides.
"""

from __future__ import annotations

import markdown

# Window chrome shared by every card. Kept out of any f-string so its literal
# CSS (e.g. ``border-radius: 50%``, the ``{`` braces) needs no escaping.
_BASE_CSS = """\
* { box-sizing: border-box; }
/* The canvas stays white on purpose: htmlshot crops the card out of it by
   difference-from-white, so a themed body is a card the height of the canvas. */
body { margin: 0; background: #ffffff;
       font-family: var(--font, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif); }
.window { margin: 16px auto; background: var(--c-page, #ffffff); border: 1px solid var(--c-line, #d0d7de);
          border-radius: 14px; overflow: hidden; box-shadow: 0 12px 34px rgba(16,26,54,0.13); }
.titlebar { display: flex; align-items: center; height: 54px; padding: 0 20px;
            background: var(--c-surface, #f2f3f5); border-bottom: 1px solid var(--c-line, #e2e4e8);
            position: relative; }
.dot { width: 14px; height: 14px; border-radius: 50%; margin-right: 9px; }
.r { background: #ff5f56; } .y { background: #ffbd2e; } .g { background: #27c93f; }
.fname { position: absolute; left: 0; right: 0; text-align: center;
         font-family: var(--font-mono, ui-monospace, "SF Mono", Menlo, monospace); font-size: 19px;
         color: var(--c-muted, #6b7280); }
"""

# Default document typography for :func:`markdown_card` (scoped to ``.content``).
_CONTENT_CSS = """\
.content { padding: 40px 52px 48px; font-size: 24px; line-height: 1.58; color: var(--c-ink, #1f2328); }
.content h1 { font-size: 42px; font-weight: 600; margin: 0 0 16px; padding-bottom: 14px;
              border-bottom: 1px solid var(--c-line, #d0d7de); letter-spacing: -0.01em; }
.content h2 { font-size: 30px; font-weight: 600; margin: 30px 0 12px; padding-bottom: 9px;
              border-bottom: 1px solid var(--c-line, #d0d7de); }
.content h3 { font-size: 25px; font-weight: 600; margin: 22px 0 10px; }
.content p { margin: 0 0 16px; }
.content a { color: var(--c-accent-1, #3b5bdb); text-decoration: none; }
.content code { font-family: var(--font-mono, ui-monospace, "SF Mono", Menlo, monospace); font-size: 0.85em;
                background: var(--c-surface, #eff1f3); padding: 2px 7px; border-radius: 6px;
                color: var(--c-ink, #1f2328); }
.content pre { background: var(--c-surface, #f6f8fa); border: 1px solid var(--c-line, #e2e4e8);
               border-radius: 10px; padding: 16px 20px; overflow-x: auto; margin: 0 0 16px; }
.content pre code { background: none; padding: 0; font-size: 19px; line-height: 1.45;
                    color: var(--c-ink, #1f2328); }
.content ul { padding-left: 28px; margin: 0 0 16px; }
.content li { margin: 7px 0; }
.content hr { border: 0; border-top: 1px solid var(--c-line, #d0d7de); margin: 24px 0; }
.content em { font-style: italic; }
.content strong { font-weight: 700; }
"""

# Sizes suit a compact card; scale up via the ``extra_css`` argument.
_TREE_CSS = """\
.content { padding: 15px 22px 17px; }
.folder { font-size: 20px; font-weight: 700; color: var(--c-ink, #1f2328); margin: 0 0 9px; }
.folder .cnt { font-weight: 600; color: var(--c-muted, #6b7280); font-size: 15px; }
.row { font-family: ui-monospace, "SF Mono", Menlo, monospace; font-size: 16px;
       color: var(--c-ink, #1f2328); padding: 6px 0; white-space: nowrap; }
.row .ico { margin-right: 9px; }
.row.sub { color: var(--c-ink, #1f2328); font-weight: 700; }
.row.hi { color: var(--c-accent-1, #3b5bdb); font-weight: 700; background: #fff4ea;
          border-radius: 7px; margin-left: -2px; }
.more { font-family: ui-monospace, "SF Mono", Menlo, monospace; font-size: 14px;
        color: #9aa3b2; padding: 8px 0 0 20px; font-style: italic; }
"""

_DEFAULT_EXTENSIONS = ["extra"]


def window_card(
    body_html: str,
    *,
    filename: str,
    max_width: int = 1000,
    extra_css: str = "",
    body_class: str = "content",
) -> str:
    """Wrap ``body_html`` in the window frame and return a full HTML document.

    Args:
        body_html: Inner HTML placed in the card body.
        filename: Label shown centered in the titlebar.
        max_width: Card width in pixels.
        extra_css: CSS appended after the base chrome — style the body here
            (e.g. the ``.content`` block that :func:`markdown_card` supplies).
        body_class: CSS class on the body wrapper div.
    """
    style = f"{_BASE_CSS}.window {{ max-width: {max_width}px; }}\n{extra_css}"
    return (
        '<!doctype html><html><head><meta charset="utf-8"><style>\n'
        f"{style}"
        "</style></head><body>\n"
        '<div class="window">\n'
        '  <div class="titlebar"><span class="dot r"></span><span class="dot y"></span>'
        '<span class="dot g"></span>\n'
        f'  <span class="fname">{filename}</span></div>\n'
        f'  <div class="{body_class}">{body_html}</div>\n'
        "</div>\n</body></html>"
    )


def markdown_card(
    md_text: str,
    *,
    filename: str,
    extensions: list[str] | None = None,
    content_css: str = "",
    max_width: int = 1000,
) -> str:
    """Render ``md_text`` to HTML and wrap it in a window card.

    Args:
        md_text: Markdown source.
        filename: Label shown in the titlebar.
        extensions: python-markdown extensions (default ``["extra"]``; pass
            ``["extra", "fenced_code"]`` for fenced code blocks).
        content_css: CSS appended after the default document typography to
            override specific rules.
        max_width: Card width in pixels.
    """
    body = markdown.markdown(md_text, extensions=extensions or _DEFAULT_EXTENSIONS)
    return window_card(
        body, filename=filename, max_width=max_width, extra_css=_CONTENT_CSS + content_css
    )


def filetree_card(
    folder: str,
    rows: list[tuple[str, str, int]],
    *,
    filename: str,
    count: str | None = None,
    more: str | None = None,
    max_width: int = 470,
    extra_css: str = "",
    indent_base: int = 20,
    indent_step: int = 22,
) -> str:
    """Render a file-explorer tree (folder header + rows) as a window card.

    Args:
        folder: Top folder name (rendered with a 📁 and the optional ``count``).
        rows: One ``(label, kind, level)`` per row. ``kind`` is ``"file"``,
            ``"folder"`` (a subfolder), or ``"hi"`` (a highlighted file); ``level``
            is the indent depth (0 = directly inside ``folder``).
        filename: Titlebar label, e.g. a breadcrumb ``"project / .ai / rules"``.
        count: Optional dimmed count beside the folder, e.g. ``"53 files"``.
        more: Optional footer line, e.g. ``"+ 41 more"``.
        max_width: Card width in pixels.
        extra_css: CSS appended after the tree defaults (e.g. to scale fonts up).
        indent_base: Left padding (px) of a level-0 row.
        indent_step: Extra left padding (px) per indent level.
    """
    icon = {"file": "📄", "folder": "📁", "hi": "📄"}
    parts = [f'<div class="folder">📁 {folder}']
    if count:
        parts.append(f'&nbsp;&nbsp;<span class="cnt">{count}</span>')
    parts.append("</div>")
    for label, kind, level in rows:
        cls = {"hi": "row hi", "folder": "row sub"}.get(kind, "row")
        pad = indent_base + level * indent_step
        parts.append(
            f'<div class="{cls}" style="padding-left:{pad}px">'
            f'<span class="ico">{icon[kind]}</span>{label}</div>'
        )
    if more:
        parts.append(f'<div class="more">{more}</div>')
    return window_card(
        "".join(parts), filename=filename, max_width=max_width, extra_css=_TREE_CSS + extra_css
    )
