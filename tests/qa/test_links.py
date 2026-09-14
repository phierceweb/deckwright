"""The `link` check reads the saved package. Every case is a real saved deck."""

from __future__ import annotations

from pptx import Presentation
from pptx.util import Inches

from deckwright.qa.links import check_links
from deckwright.utils.links import web_address_problem
from deckwright.qa.model import Severity
from deckwright.qa.package import check_package
from deckwright.utils.deck import delete_slide


def _deck(tmp_path, slides=2):
    prs = Presentation()
    for _ in range(slides):
        prs.slides.add_slide(prs.slide_layouts[6])
    box = prs.slides[0].shapes.add_textbox(Inches(1), Inches(1), Inches(3), Inches(1))
    box.text_frame.text = "click"
    return prs, box


def _saved(tmp_path, prs):
    path = tmp_path / "d.pptx"
    prs.save(str(path))
    return path


def test_a_jump_to_a_slide_in_the_show_is_clean(tmp_path):
    prs, box = _deck(tmp_path)
    box.click_action.target_slide = prs.slides[1]
    assert check_links(_saved(tmp_path, prs)) == []


def test_a_jump_to_a_slide_no_longer_in_the_show_is_an_error(tmp_path):
    """The relationship still resolves to a part, so `relationship` passes it."""
    prs, box = _deck(tmp_path, slides=3)
    box.click_action.target_slide = prs.slides[2]
    delete_slide(prs, 2)
    findings = check_links(_saved(tmp_path, prs))
    assert [(f.slide, f.check, f.severity) for f in findings] == [(1, "link", Severity.ERROR)]
    assert "not a slide in this show" in findings[0].detail


def test_a_relative_jump_is_clean_and_is_not_a_dangling_relationship(tmp_path):
    prs, box = _deck(tmp_path)
    hlink = box._element.nvSpPr.cNvPr.get_or_add_hlinkClick()
    hlink.set("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id", "")
    hlink.action = "ppaction://hlinkshowjump?jump=lastslide"
    path = _saved(tmp_path, prs)
    assert check_links(path) == []
    assert [f for f in check_package(path) if f.check == "relationship"] == []


def test_a_relative_jump_no_show_knows_is_a_warning(tmp_path):
    prs, box = _deck(tmp_path)
    hlink = box._element.nvSpPr.cNvPr.get_or_add_hlinkClick()
    hlink.action = "ppaction://hlinkshowjump?jump=sideways"
    findings = check_links(_saved(tmp_path, prs))
    assert [(f.check, f.severity) for f in findings] == [("link", Severity.WARN)]
    assert "'sideways'" in findings[0].detail


def test_a_web_link_on_a_run_is_checked_by_its_address(tmp_path):
    prs, box = _deck(tmp_path)
    run = box.text_frame.paragraphs[0].runs[0]
    run.hyperlink.address = "javascript:alert(1)"
    findings = check_links(_saved(tmp_path, prs))
    assert [(f.check, f.severity) for f in findings] == [("link", Severity.WARN)]
    assert "not a web address" in findings[0].detail


def test_a_well_formed_web_link_is_clean(tmp_path):
    prs, box = _deck(tmp_path)
    box.text_frame.paragraphs[0].runs[0].hyperlink.address = "https://example.com/a?b=c"
    assert check_links(_saved(tmp_path, prs)) == []


def test_web_addresses():
    assert web_address_problem("https://example.com") is None
    assert web_address_problem("mailto:someone@example.com") is None
    assert "names no email address" in web_address_problem("mailto:someone")
    assert "needs a host" in web_address_problem("https:///path")
    assert "needs a host" in web_address_problem("https://exa mple.com")
    assert "not a web address" in web_address_problem("file:///etc/passwd")
    assert "not a web address" in web_address_problem("example.com")


def test_a_link_to_a_part_inside_the_package_is_not_judged_as_a_web_address(tmp_path):
    from pptx.opc.constants import RELATIONSHIP_TYPE as RT

    prs, box = _deck(tmp_path)
    rid = prs.slides[0].part.relate_to(prs.slides[1].part, RT.SLIDE)
    box._element.nvSpPr.cNvPr.get_or_add_hlinkClick().set(
        "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id", rid
    )
    assert check_links(_saved(tmp_path, prs)) == []


def test_the_end_show_and_last_slide_viewed_actions_are_jumps_a_show_follows(tmp_path):
    prs, box = _deck(tmp_path)
    hlink = box._element.nvSpPr.cNvPr.get_or_add_hlinkClick()
    hlink.action = "ppaction://hlinkshowjump?jump=endshow"
    other = prs.slides[1].shapes.add_textbox(0, 0, Inches(1), Inches(1))
    other._element.nvSpPr.cNvPr.get_or_add_hlinkClick().action = (
        "ppaction://hlinkshowjump?jump=lastslideviewed"
    )
    assert check_links(_saved(tmp_path, prs)) == []


def test_a_mouse_over_slide_jump_on_a_run_is_checked(tmp_path):
    prs, box = _deck(tmp_path, slides=3)
    run = box.text_frame.paragraphs[0].runs[0]
    run.hyperlink.address = "https://example.com"
    rpr = run._r.rPr
    hlink = rpr.find("{http://schemas.openxmlformats.org/drawingml/2006/main}hlinkClick")
    rid = prs.slides[0].part.relate_to(
        prs.slides[2].part,
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide",
    )
    over = hlink.makeelement(
        "{http://schemas.openxmlformats.org/drawingml/2006/main}hlinkMouseOver"
    )
    over.set("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id", rid)
    over.set("action", "ppaction://hlinksldjump")
    hlink.addnext(over)
    delete_slide(prs, 2)
    findings = check_links(_saved(tmp_path, prs))
    assert [f.severity for f in findings] == [Severity.ERROR]


def test_an_empty_reference_outside_a_click_action_is_still_a_dangling_relationship(
    tmp_path, png=None
):
    from PIL import Image

    image = tmp_path / "p.png"
    Image.new("RGB", (4, 4)).save(image)
    prs, box = _deck(tmp_path)
    picture = prs.slides[0].shapes.add_picture(str(image), 0, 0)
    picture._element.blipFill.blip.set(
        "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed", ""
    )
    findings = [f for f in check_package(_saved(tmp_path, prs)) if f.check == "relationship"]
    assert len(findings) == 1


def test_an_external_link_is_the_link_checks_to_judge_not_a_missing_part(tmp_path):
    prs, box = _deck(tmp_path)
    box.text_frame.paragraphs[0].runs[0].hyperlink.address = "file:///Users/me/report.pdf"
    path = _saved(tmp_path, prs)
    assert [f for f in check_package(path) if f.check == "relationship"] == []
    assert [f.severity for f in check_links(path)] == [Severity.WARN]
