import io

import pytest
from PIL import Image

from deckwright.panels.model import Panel, Region
from deckwright.panels.place import place_panel


@pytest.fixture
def fake_render(tmp_path, monkeypatch):
    """Stand in for headless Chrome: write a solid PNG of the requested size."""
    monkeypatch.setenv("DECKWRIGHT_CACHE_DIR", str(tmp_path))

    def render(html, path, width, scale):
        Image.new("RGB", (width * scale, 400 * scale), "white").save(path)
        return str(path)

    return render


def test_an_unsliced_panel_places_one_picture(ctx_factory, fake_render):
    ctx = ctx_factory({"title": "T"})
    panel = Panel(html="<b>x</b>", width=700)
    placed = place_panel(ctx, panel, left=1.0, top=2.0, width=6.0, render=fake_render)
    assert list(placed) == [""]
    assert len(ctx.slide.shapes) == 1


def test_slicing_places_one_picture_per_region(ctx_factory, fake_render):
    ctx = ctx_factory({"title": "T"})
    panel = Panel(
        html="<b>x</b>",
        width=700,
        regions=(Region("top", 0, 0, 700, 200), Region("bottom", 0, 200, 700, 200)),
    )
    placed = place_panel(
        ctx, panel, left=1.0, top=2.0, width=6.0, slice_by="region", render=fake_render
    )
    assert sorted(placed) == ["bottom", "top"]
    assert len(ctx.slide.shapes) == 2


def test_the_panel_renders_only_once_when_sliced(ctx_factory, tmp_path, monkeypatch):
    monkeypatch.setenv("DECKWRIGHT_CACHE_DIR", str(tmp_path))
    calls = []

    def render(html, path, width, scale):
        calls.append(html)
        Image.new("RGB", (width * scale, 400 * scale), "white").save(path)
        return str(path)

    ctx = ctx_factory({"title": "T"})
    panel = Panel(
        html="<b>x</b>",
        width=700,
        regions=(Region("a", 0, 0, 700, 200), Region("b", 0, 200, 700, 200)),
    )
    place_panel(ctx, panel, left=1.0, top=2.0, width=6.0, slice_by="region", render=render)
    assert len(calls) == 1


def test_sliced_pictures_stack_without_overlap(ctx_factory, fake_render):
    ctx = ctx_factory({"title": "T"})
    panel = Panel(
        html="<b>x</b>",
        width=700,
        regions=(Region("a", 0, 0, 700, 200), Region("b", 0, 200, 700, 200)),
    )
    placed = place_panel(
        ctx, panel, left=1.0, top=2.0, width=6.0, slice_by="region", render=fake_render
    )
    a, b = placed["a"], placed["b"]
    assert a.top + a.height == pytest.approx(b.top, abs=1)


def test_every_placed_picture_is_recorded_as_an_image(ctx_factory, fake_render):
    ctx = ctx_factory({"title": "T"})
    panel = Panel(html="<b>x</b>", width=700)
    place_panel(ctx, panel, left=1.0, top=2.0, width=6.0, render=fake_render)
    assert [s.rendered for s in ctx.manifest.slides[0].shapes] == ["image"]


def test_every_sliced_picture_is_recorded_as_an_image(ctx_factory, fake_render):
    ctx = ctx_factory({"title": "T"})
    panel = Panel(
        html="<b>x</b>",
        width=700,
        regions=(Region("a", 0, 0, 700, 200), Region("b", 0, 200, 700, 200)),
    )
    place_panel(ctx, panel, left=1.0, top=2.0, width=6.0, slice_by="region", render=fake_render)
    assert [s.rendered for s in ctx.manifest.slides[0].shapes] == ["image", "image"]


def test_slicing_an_unregioned_panel_is_rejected(ctx_factory, fake_render):
    from deckwright.errors import LayoutError

    ctx = ctx_factory({"title": "T"})
    with pytest.raises(LayoutError, match="no regions"):
        place_panel(
            ctx,
            Panel(html="x", width=700),
            left=1.0,
            top=2.0,
            width=6.0,
            slice_by="region",
            render=fake_render,
        )


def test_width_and_height_are_mutually_exclusive(ctx_factory, fake_render):
    from deckwright.errors import LayoutError

    ctx = ctx_factory({"title": "T"})
    with pytest.raises(LayoutError, match="exactly one"):
        place_panel(
            ctx,
            Panel(html="x", width=700),
            left=1.0,
            top=2.0,
            width=6.0,
            height=3.0,
            render=fake_render,
        )


def test_max_height_rejects_a_picture_taller_than_the_budget(ctx_factory, fake_render):
    from deckwright.errors import LayoutError

    ctx = ctx_factory({"title": "T"})
    # fake_render's fixed aspect makes width=6.0 place ~3.43in tall — over a 1.0in budget.
    with pytest.raises(LayoutError, match=r"slide 1.*3\.43in tall.*1\.00in budget"):
        place_panel(
            ctx,
            Panel(html="x", width=700),
            left=1.0,
            top=2.0,
            width=6.0,
            max_height=1.0,
            render=fake_render,
        )


def test_a_picture_within_the_budget_is_placed_normally(ctx_factory, fake_render):
    ctx = ctx_factory({"title": "T"})
    placed = place_panel(
        ctx,
        Panel(html="x", width=700),
        left=1.0,
        top=2.0,
        width=6.0,
        max_height=10.0,
        render=fake_render,
    )
    assert list(placed) == [""]


def test_a_region_that_overflows_the_rendered_panel_is_rejected(ctx_factory, fake_render):
    from deckwright.errors import LayoutError

    ctx = ctx_factory({"title": "T"})
    # fake_render always renders a fixed 400px-tall panel; this region's bottom edge
    # (600) falls outside it — the case Image.crop() would silently zero-pad instead.
    panel = Panel(html="<b>x</b>", width=700, regions=(Region("b", 0, 200, 700, 400),))
    with pytest.raises(LayoutError, match=r"region 'b'.*does not fit"):
        place_panel(ctx, panel, left=1.0, top=2.0, width=6.0, slice_by="region", render=fake_render)


def test_each_region_is_cut_from_its_own_part_of_the_panel(ctx_factory, tmp_path, monkeypatch):
    monkeypatch.setenv("DECKWRIGHT_CACHE_DIR", str(tmp_path))

    def render(html, path, *, width, scale):
        img = Image.new("RGB", (width * scale, 400 * scale), "red")
        img.paste("blue", (0, 200 * scale, width * scale, 400 * scale))
        img.save(path)
        return str(path)

    ctx = ctx_factory({"title": "T"})
    panel = Panel(
        html="<b>x</b>",
        width=700,
        regions=(Region("a", 0, 0, 700, 200), Region("b", 0, 200, 700, 200)),
    )
    placed = place_panel(ctx, panel, left=1.0, top=2.0, width=6.0, slice_by="region", render=render)

    def middle(pic):
        im = Image.open(io.BytesIO(pic.image.blob)).convert("RGB")
        return im.getpixel((im.width // 2, im.height // 2))

    assert middle(placed["a"]) == (255, 0, 0)
    assert middle(placed["b"]) == (0, 0, 255)
