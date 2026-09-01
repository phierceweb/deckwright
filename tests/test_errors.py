import zipfile

import pytest
from pptx import Presentation
from pptx.exc import PackageNotFoundError

from pf_core.exceptions import (
    AppError,
    ClientError,
    ConfigurationError,
    FlowException,
    InvalidInputError,
)

from deckwright.errors import LayoutError, RenderError, SpecError, ThemeError
from deckwright.utils.deck import open_presentation


def test_spec_error_is_a_flow_exception():
    assert issubclass(SpecError, InvalidInputError)
    assert issubclass(SpecError, FlowException)


def test_theme_error_is_a_configuration_error():
    assert issubclass(ThemeError, ConfigurationError)


def test_layout_error_is_a_flow_exception():
    assert issubclass(LayoutError, InvalidInputError)


def test_render_error_is_an_app_error():
    assert issubclass(RenderError, ClientError)
    assert issubclass(RenderError, AppError)


def test_spec_error_carries_its_message():
    with pytest.raises(SpecError, match=r"slide 3: unknown layout 'bogus'"):
        raise SpecError("slide 3: unknown layout 'bogus'")


_RELS_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
_OFFICE_DOCUMENT = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"
)
_WORD_MAIN = "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"


def _prose(path):
    path.write_text("Dear team, the deck is attached.")
    return path


def _zip_without_content_types(path):
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("hello.txt", "hi")
    return path


def _word_package(path):
    """A well-formed OPC package whose main part is Word's — a renamed .docx."""
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(
            "[Content_Types].xml",
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            f'<Override PartName="/word/document.xml" ContentType="{_WORD_MAIN}"/></Types>',
        )
        z.writestr(
            "_rels/.rels",
            f'<Relationships xmlns="{_RELS_NS}"><Relationship Id="rId1" '
            f'Type="{_OFFICE_DOCUMENT}" Target="word/document.xml"/></Relationships>',
        )
        z.writestr(
            "word/document.xml",
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            "<w:body/></w:document>",
        )
    return path


@pytest.mark.parametrize(
    "make, raw",
    [
        (_prose, PackageNotFoundError),
        (_zip_without_content_types, KeyError),
        (_word_package, ValueError),
    ],
)
def test_every_shape_of_unreadable_pptx_becomes_the_error_the_caller_named(tmp_path, make, raw):
    """python-pptx spells "not a .pptx" in three classes sharing no base below ``Exception``, so
    nothing narrower catches all of them."""
    path = make(tmp_path / "d.pptx")
    with pytest.raises(raw):
        Presentation(str(path))

    with pytest.raises(SpecError) as caught:
        open_presentation(path, what="deck", error=SpecError)

    assert f"deck {path} is not a readable .pptx" in str(caught.value)
    assert isinstance(caught.value.__cause__, raw)
