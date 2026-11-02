"""The pictures a card's HTML names, embedded from beside its source or refused by name."""

from __future__ import annotations

import pytest

from deckwright.services.card_pictures import UnembeddableImage, inline_local_images
from deckwright.services.htmlcard import markdown_card


def test_a_relative_image_beside_the_source_becomes_a_data_uri(tmp_path):
    """The card's policy refuses `file:` on purpose, so a local picture travels inside the page."""
    (tmp_path / "pic.png").write_bytes(b"\x89PNG\r\n\x1a\nfake")
    html = inline_local_images('<p><img alt="a" src="pic.png" /></p>', tmp_path)
    assert html == '<p><img alt="a" src="data:image/png;base64,iVBORw0KGgpmYWtl" /></p>'


def test_web_and_data_images_are_left_for_the_browser(tmp_path):
    html = (
        '<img src="https://x/y.png"><img src="data:image/gif;base64,R0lG"><img src><img src="">'
        '<img srcset="https://x/a.png  1x,https://x/b.png 2x"><video><source src="clip.mp4"></video>'
        "<p style='background: url(https://x/y.png), url(data:image/gif;base64,R0lG); "
        "filter: url(#blur)'><div srcset='gone.png'></div>"
        "<svg><image href='https://x/y.png'/><use href='#dot'/><image href='#dot'/></svg>"
        "<a href='pic.png'>a link is not a picture</a>"
    )
    assert inline_local_images(html, tmp_path) == html


def test_a_picture_is_embedded_only_from_the_sources_own_directory(tmp_path):
    """The markdown behind a card is often someone else's. A path that climbs out of its folder,
    or names a file elsewhere, could carry a private picture into the deck at an opacity nobody
    sees, which is what the card's content policy exists to stop."""
    (tmp_path / "private.png").write_bytes(b"x")
    docs = tmp_path / "docs"
    (docs / "img").mkdir(parents=True)
    (docs / "img" / "own.png").write_bytes(b"x")

    inside = inline_local_images(f'<img src="{docs / "img" / "own.png"}">', docs)
    assert inside == '<img src="data:image/png;base64,eA==">'
    assert inline_local_images('<img src="img/../img/own.png">', docs) == inside
    for escaping in ("../private.png", str(tmp_path / "private.png")):
        for tag in (
            f'<img src="{escaping}">',
            f"<img src='{escaping}'>",
            f"<img src={escaping}>",
            f"<picture><source srcset='{escaping} 2x'></picture>",
            f"<div style='background: url(\"{escaping}\")'></div>",
            f"<style>.logo {{ background-image: url({escaping}) }}</style>",
            f'<svg><image href="{escaping}"/></svg>',
            f'<svg><image xlink:href="{escaping}"/></svg>',
            f"<video poster='{escaping}'></video>",
        ):
            with pytest.raises(UnembeddableImage) as refused:
                inline_local_images(tag, docs)
            assert (refused.value.reason, refused.value.src) == ("outside", escaping)


def test_every_local_candidate_in_a_srcset_is_embedded_and_the_rest_kept(tmp_path):
    """A browser picks its picture from `srcset` over `src`, and a `<picture>` whose dark-mode
    `<source>` names a second file is how a README ships a logo; either left unread is a
    `file:` picture the card's policy blanks."""
    (tmp_path / "pic.png").write_bytes(b"x")
    (tmp_path / "dark.png").write_bytes(b"y")
    pic, dark = "data:image/png;base64,eA==", "data:image/png;base64,eQ=="
    html = (
        "<picture><source media='(prefers-color-scheme: dark)' srcset=dark.png>"
        '<img srcset="data:image/gif;base64,R0lG 1x,pic.png 2x, https://x/y.png?a=1&amp;b=2 3x"'
        ' src="pic.png"></picture><img srcset="pic.png, dark.png 2x">'
    )
    assert inline_local_images(html, tmp_path) == (
        f"<picture><source media='(prefers-color-scheme: dark)' srcset=\"{dark}\">"
        f'<img srcset="data:image/gif;base64,R0lG 1x, {pic} 2x, https://x/y.png?a=1&amp;b=2 3x"'
        f' src="{pic}"></picture><img srcset="{pic}, {dark} 2x">'
    )


def test_a_css_url_names_a_picture_in_a_style_attribute_or_a_style_block(tmp_path):
    """CSS reaches a picture through `url()` as surely as `<img>` does, and the card's policy
    blanks a `file:` one just the same. A font the CSS names is not a picture, and is left."""
    (tmp_path / "pic.png").write_bytes(b"x")
    (tmp_path / "face.woff2").write_bytes(b"f")
    pic = "data:image/png;base64,eA=="
    html = (
        "<style>.hero { background: url( 'pic.png' ) }"
        " @font-face { src: url(face.woff2) }</style>"
        '<div style="background: url(&quot;pic.png&quot;) no-repeat, url(pic.png)">x</div>'
    )
    assert inline_local_images(html, tmp_path) == (
        f'<style>.hero {{ background: url("{pic}") }} @font-face {{ src: url(face.woff2) }}</style>'
        f'<div style="background: url(&quot;{pic}&quot;) no-repeat, url(&quot;{pic}&quot;)">x</div>'
    )


def test_an_svg_image_names_its_picture_by_href_or_xlink_href(tmp_path):
    """Inline SVG in the markdown draws a picture with `<image>`, which reads `href`, or
    `xlink:href` in SVG written before SVG 2."""
    (tmp_path / "pic.png").write_bytes(b"x")
    pic = "data:image/png;base64,eA=="
    html = '<svg><image href="pic.png" width="9"/><image xlink:href=\'pic.png\'/></svg>'
    assert inline_local_images(html, tmp_path) == (
        f'<svg><image href="{pic}" width="9"/><image xlink:href="{pic}"/></svg>'
    )


@pytest.mark.parametrize(
    "tag",
    [
        "<img src='pic.png' alt='a'>",
        "<img src=pic.png alt=a>",
        '<image src="pic.png">',
        '<IMG SRC = " pic.png ">',
        '<img alt="a > b" src="pic.png">',
        '<img alt="see src=gone.png" data-src="gone.png" src="pic.png">',
    ],
)
def test_raw_html_names_a_picture_however_its_src_is_written(tmp_path, tag):
    """Raw HTML in the markdown reaches the browser as written; a `src` left unread would be a
    `file:` picture the card's policy blanks, and the build would say nothing."""
    (tmp_path / "pic.png").write_bytes(b"x")
    assert 'src="data:image/png;base64,eA=="' in inline_local_images(tag, tmp_path)


def test_a_video_poster_is_a_picture(tmp_path):
    """The card cannot play a video, so its poster frame is all of it that shows."""
    (tmp_path / "pic.png").write_bytes(b"x")
    assert inline_local_images("<video poster=pic.png controls></video>", tmp_path) == (
        '<video poster="data:image/png;base64,eA==" controls></video>'
    )


def test_a_percent_escape_or_an_entity_in_a_name_is_the_file_it_spells(tmp_path):
    """`%20` is how editors write a space in a markdown link, and markdown writes `&` as
    `&amp;`; the browser decodes both, so the file on disk is the decoded name."""
    (tmp_path / "my pic.png").write_bytes(b"x")
    (tmp_path / "a&b.png").write_bytes(b"x")
    html = markdown_card("![s](my%20pic.png) ![e](a&b.png)", filename="f.md", image_base=tmp_path)
    assert html.count('src="data:image/png;base64,eA=="') == 2
    with pytest.raises(UnembeddableImage) as missing:
        inline_local_images('<img src="no%20such.png">', tmp_path)
    assert missing.value.src == "no%20such.png"


def test_a_missing_image_and_a_file_that_is_no_image_are_each_named(tmp_path):
    with pytest.raises(UnembeddableImage) as missing:
        inline_local_images('<img src="gone.png">', tmp_path)
    (tmp_path / "notes.txt").write_text("words")
    with pytest.raises(UnembeddableImage) as wrong_kind:
        inline_local_images('<img src="notes.txt">', tmp_path)
    assert (missing.value.reason, missing.value.src) == ("missing", "gone.png")
    assert (wrong_kind.value.reason, wrong_kind.value.src) == ("not-image", "notes.txt")
