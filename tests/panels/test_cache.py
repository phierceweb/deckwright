from pathlib import Path

import pytest

from deckwright.errors import RenderError
from deckwright.panels import cache
from deckwright.panels.cache import cache_key, cached_png
from deckwright.panels.model import Panel

PANEL = Panel(html="<b>hello</b>", width=700)


def _recorder(tmp_path):
    calls = []

    def render(html, path, *, width, scale):
        calls.append(html)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_bytes(b"PNGDATA")
        return str(path)

    return render, calls


def test_the_key_changes_with_the_html():
    a = cache_key("<b>a</b>", width=700, scale=2, theme_hash="t")
    b = cache_key("<b>b</b>", width=700, scale=2, theme_hash="t")
    assert a != b


def test_the_key_changes_with_the_theme_hash():
    a = cache_key("x", width=700, scale=2, theme_hash="one")
    b = cache_key("x", width=700, scale=2, theme_hash="two")
    assert a != b


def test_the_key_changes_with_the_content_policy(monkeypatch):
    """Else a tightened policy is defeated by every PNG rendered under the old one."""
    a = cache_key("x", width=700, scale=2, theme_hash="t")
    monkeypatch.setattr(cache, "CSP_META", '<meta content="other">')
    assert cache_key("x", width=700, scale=2, theme_hash="t") != a


def test_the_key_changes_with_width_and_scale():
    base = cache_key("x", width=700, scale=2, theme_hash="t")
    assert cache_key("x", width=800, scale=2, theme_hash="t") != base
    assert cache_key("x", width=700, scale=3, theme_hash="t") != base


def test_the_key_is_stable():
    assert cache_key("x", width=700, scale=2, theme_hash="t") == cache_key(
        "x", width=700, scale=2, theme_hash="t"
    )


def test_a_miss_renders_once(tmp_path, monkeypatch):
    monkeypatch.setenv("DECKWRIGHT_CACHE_DIR", str(tmp_path))
    render, calls = _recorder(tmp_path)
    png = cached_png(PANEL, scale=2, theme_hash="t", render=render)
    assert png.is_file()
    assert len(calls) == 1


def test_a_hit_does_not_render_again(tmp_path, monkeypatch):
    monkeypatch.setenv("DECKWRIGHT_CACHE_DIR", str(tmp_path))
    render, calls = _recorder(tmp_path)
    cached_png(PANEL, scale=2, theme_hash="t", render=render)
    cached_png(PANEL, scale=2, theme_hash="t", render=render)
    assert len(calls) == 1


def test_a_changed_theme_hash_re_renders(tmp_path, monkeypatch):
    monkeypatch.setenv("DECKWRIGHT_CACHE_DIR", str(tmp_path))
    render, calls = _recorder(tmp_path)
    cached_png(PANEL, scale=2, theme_hash="one", render=render)
    cached_png(PANEL, scale=2, theme_hash="two", render=render)
    assert len(calls) == 2


def test_the_cache_dir_comes_from_the_env(tmp_path, monkeypatch):
    monkeypatch.setenv("DECKWRIGHT_CACHE_DIR", str(tmp_path / "elsewhere"))
    render, _ = _recorder(tmp_path)
    png = cached_png(PANEL, scale=2, theme_hash="t", render=render)
    assert (tmp_path / "elsewhere") in png.parents


def test_a_renderer_that_writes_nothing_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("DECKWRIGHT_CACHE_DIR", str(tmp_path))

    def render(html, path, *, width, scale):
        return str(path)

    with pytest.raises(RenderError):
        cached_png(PANEL, scale=2, theme_hash="t", render=render)

    key = cache_key(PANEL.html, width=PANEL.width, scale=2, theme_hash="t")
    assert not (tmp_path / "panels" / f"{key}.png").exists()


def test_a_crash_after_writing_leaves_nothing_cached_and_a_retry_succeeds(tmp_path, monkeypatch):
    monkeypatch.setenv("DECKWRIGHT_CACHE_DIR", str(tmp_path))
    key = cache_key(PANEL.html, width=PANEL.width, scale=2, theme_hash="t")

    def crashing_render(html, path, *, width, scale):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_bytes(b"PARTIAL")
        raise RuntimeError("renderer crashed mid-shot")

    with pytest.raises(RuntimeError):
        cached_png(PANEL, scale=2, theme_hash="t", render=crashing_render)

    assert not (tmp_path / "panels" / f"{key}.png").exists()

    render, calls = _recorder(tmp_path)
    png = cached_png(PANEL, scale=2, theme_hash="t", render=render)
    assert png.is_file()
    assert len(calls) == 1


def test_the_renderer_is_given_a_path_ending_in_png(tmp_path, monkeypatch):
    """A renderer is entitled to infer its output format from the path's extension."""
    monkeypatch.setenv("DECKWRIGHT_CACHE_DIR", str(tmp_path))
    seen_paths = []

    def render(html, path, *, width, scale):
        seen_paths.append(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_bytes(b"PNGDATA")
        return str(path)

    cached_png(PANEL, scale=2, theme_hash="t", render=render)
    assert seen_paths[0].endswith(".png")


def test_an_empty_file_raises_render_error_and_caches_nothing(tmp_path, monkeypatch):
    monkeypatch.setenv("DECKWRIGHT_CACHE_DIR", str(tmp_path))
    key = cache_key(PANEL.html, width=PANEL.width, scale=2, theme_hash="t")

    def empty_render(html, path, *, width, scale):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_bytes(b"")
        return str(path)

    with pytest.raises(RenderError):
        cached_png(PANEL, scale=2, theme_hash="t", render=empty_render)

    assert not (tmp_path / "panels" / f"{key}.png").exists()
