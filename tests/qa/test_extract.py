import pytest

from deckwright.errors import RenderError
from deckwright.qa.textflow import extract_pages


def _fake_pdftotext(tmp_path, stdout: str, *, code: int = 0):
    """A stand-in binary that prints fixed text — keeps the test off Poppler."""
    script = tmp_path / "fake_pdftotext"
    script.write_text("#!/bin/sh\n" + f"printf '%b' \"{stdout}\"\n" + f"exit {code}\n")
    script.chmod(0o755)
    return str(script)


def _argv_recorder(tmp_path):
    """A stand-in binary that records the arguments it was handed."""
    argv = tmp_path / "argv.txt"
    script = tmp_path / "argv_pdftotext"
    script.write_text(f'#!/bin/sh\necho "$@" > {argv}\nprintf "page\\f"\n')
    script.chmod(0o755)
    return str(script), argv


def test_reading_order_is_the_default(tmp_path):
    pdf = tmp_path / "d.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    binary, argv = _argv_recorder(tmp_path)
    extract_pages(pdf, pdftotext=binary)
    assert "-layout" not in argv.read_text()


def test_layout_mode_is_requestable(tmp_path):
    pdf = tmp_path / "d.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    binary, argv = _argv_recorder(tmp_path)
    extract_pages(pdf, layout=True, pdftotext=binary)
    assert "-layout" in argv.read_text()


def test_pages_split_on_form_feeds(tmp_path):
    pdf = tmp_path / "d.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    binary = _fake_pdftotext(tmp_path, "one\fTwo\fThree\f")
    assert extract_pages(pdf, pdftotext=binary) == ["one", "Two", "Three"]


def test_a_trailing_empty_page_is_dropped(tmp_path):
    pdf = tmp_path / "d.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    assert extract_pages(pdf, pdftotext=_fake_pdftotext(tmp_path, "only\f")) == ["only"]


def test_a_missing_pdf_is_rejected(tmp_path):
    with pytest.raises(RenderError, match="not found"):
        extract_pages(tmp_path / "absent.pdf", pdftotext="pdftotext")


def test_a_failing_binary_raises_render_error(tmp_path):
    pdf = tmp_path / "d.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    binary = _fake_pdftotext(tmp_path, "", code=3)
    with pytest.raises(RenderError, match="pdftotext"):
        extract_pages(pdf, pdftotext=binary)


def test_a_missing_binary_raises_render_error(tmp_path):
    pdf = tmp_path / "d.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    with pytest.raises(RenderError, match="pdftotext"):
        extract_pages(pdf, pdftotext=str(tmp_path / "definitely-not-here"))


def test_the_binary_comes_from_the_env_when_unset(tmp_path, monkeypatch):
    pdf = tmp_path / "d.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    monkeypatch.setenv("DECKWRIGHT_PDFTOTEXT", _fake_pdftotext(tmp_path, "env\f"))
    assert extract_pages(pdf) == ["env"]
