"""Validate the raw OOXML `deckwright.motion` writes against ISO/IEC 29500-4:2016 — nothing else in the
project can. LibreOffice converts schema-invalid timing to PDF without complaint and `deckwright qa`
renders only a slide's final state; schema-valid is itself only a floor, since real PowerPoint is
what says whether a file opens without a repair prompt. See `docs/pptx-deck-building.md`."""

from __future__ import annotations

import copy
import io
import pathlib
import re
import zipfile

import pytest
from lxml import etree
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE
from pptx.util import Inches

from deckwright.motion import (
    add_chart_build,
    add_click_build,
    add_click_reveals,
    add_click_sequence,
    add_transition,
)
from deckwright.motion.transition import EFFECTS, SPEEDS

SCHEMA = pathlib.Path(__file__).parent / "schemas" / "ooxml" / "pml.xsd"
_PML = "http://schemas.openxmlformats.org/presentationml/2006/main"
_DML = "http://schemas.openxmlformats.org/drawingml/2006/main"
_MC = "http://schemas.openxmlformats.org/markup-compatibility/2006"
_A14 = "http://schemas.microsoft.com/office/drawing/2010/main"
_OMML = "http://schemas.openxmlformats.org/officeDocument/2006/math"


@pytest.fixture(scope="module")
def schema():
    return etree.XMLSchema(etree.parse(str(SCHEMA)))


def _deck():
    """A slide carrying the three shape kinds the builds are pointed at."""
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    box = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(2), Inches(1))
    box.text_frame.text = "text"
    blank = slide.shapes.add_textbox(Inches(1), Inches(3), Inches(2), Inches(1))
    data = CategoryChartData()
    data.categories = ["A", "B", "C"]
    data.add_series("S1", (1, 2, 3))
    data.add_series("S2", (3, 2, 1))
    frame = slide.shapes.add_chart(
        XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(4), Inches(1), Inches(4), Inches(3), data
    )
    return prs, slide, box.shape_id, blank.shape_id, frame.shape_id


def _slide_xml(prs) -> bytes:
    buf = io.BytesIO()
    prs.save(buf)
    buf.seek(0)
    return zipfile.ZipFile(buf).read("ppt/slides/slide1.xml")


def _validate(schema, prs) -> list[str]:
    doc = etree.fromstring(_slide_xml(prs))
    if schema.validate(doc):
        return []
    return [e.message for e in schema.error_log]


def _branch(root, which: str):
    """A copy of ``root`` with every ``mc:AlternateContent`` replaced by the children of its
    ``which`` branch, ``"Choice"`` or ``"Fallback"`` — the slide one reader sees.

    The vendored schemas carry no extension namespace, so what a Choice ``Requires`` is
    removed and the ISO structure around it is what gets validated.
    """
    tree = copy.deepcopy(root)
    for alternate in list(tree.iter(f"{{{_MC}}}AlternateContent")):
        parent = alternate.getparent()
        at = parent.index(alternate)
        parent.remove(alternate)
        chosen = alternate.find(f"{{{_MC}}}{which}")
        if chosen is None:
            continue
        required = {chosen.nsmap[prefix] for prefix in chosen.get("Requires", "").split()}
        for el in list(chosen.iter(tag=etree.Element)):
            if etree.QName(el).namespace in required:
                el.getparent().remove(el)
                continue
            for name in [n for n in el.attrib if etree.QName(n).namespace in required]:
                del el.attrib[name]
        for offset, child in enumerate(list(chosen)):
            parent.insert(at + offset, child)
    return tree


def _equation_slide():
    """A slide whose text box is stored as PowerPoint stores an equation: the Choice holds
    the maths in an a14 extension element, the Fallback the same box as plain text."""
    prs, slide, text, blank, chart = _deck()
    root = etree.fromstring(_slide_xml(prs))
    sp = next(
        el
        for el in root.iter(f"{{{_PML}}}sp")
        if el.find(f".//{{{_PML}}}cNvPr").get("id") == str(text)
    )
    alternate = etree.Element(f"{{{_MC}}}AlternateContent", nsmap={"mc": _MC})
    sp.addprevious(alternate)
    choice = etree.SubElement(alternate, f"{{{_MC}}}Choice", nsmap={"a14": _A14}, Requires="a14")
    maths = copy.deepcopy(sp)
    paragraph = maths.find(f".//{{{_DML}}}p")
    for child in list(paragraph):
        paragraph.remove(child)
    paragraph.append(
        etree.fromstring(
            f'<a14:m xmlns:a14="{_A14}" xmlns:m="{_OMML}"><m:oMathPara><m:oMath>'
            "<m:r><m:t>x²</m:t></m:r></m:oMath></m:oMathPara></a14:m>"
        )
    )
    choice.append(maths)
    etree.SubElement(alternate, f"{{{_MC}}}Fallback").append(sp)
    return root


@pytest.mark.parametrize("which", ["Choice", "Fallback"])
def test_each_branch_of_markup_compatibility_validates_on_its_own(schema, which):
    """`pml.xsd` has no `mc:AlternateContent`, so the wrapper itself never validates; a reader
    only ever sees one branch, and each has to be valid on its own."""
    root = _equation_slide()
    assert not schema.validate(root)

    assert schema.validate(_branch(root, which)), [e.message for e in schema.error_log]


@pytest.mark.parametrize("broken, sound", [("Choice", "Fallback"), ("Fallback", "Choice")])
def test_the_branch_gate_catches_a_fault_inside_one_branch(schema, broken, sound):
    """The negative control for the case above. A harness that dropped the wrapper, or read
    one branch for both, would pass a fault confined to a single branch."""
    root = _equation_slide()
    sp = root.find(f".//{{{_MC}}}{broken}/{{{_PML}}}sp")
    sp.remove(sp.find(f"{{{_PML}}}spPr"))

    assert schema.validate(_branch(root, sound)), [e.message for e in schema.error_log]
    assert not schema.validate(_branch(root, broken))
    assert "spPr" in schema.error_log[0].message


def _morph_slide():
    """A slide that arrives by morph and also carries a build, so the wrapper has a
    `p:timing` to sit in front of."""
    prs, slide, text, blank, chart = _deck()
    add_click_build(slide, [text])
    add_transition(slide, "morph", speed="slow")
    return etree.fromstring(_slide_xml(prs))


@pytest.mark.parametrize("which", ["Choice", "Fallback"])
def test_each_branch_of_a_morph_transition_validates_on_its_own(schema, which):
    assert schema.validate(_branch(_morph_slide(), which)), [e.message for e in schema.error_log]


def test_the_gate_catches_a_morph_wrapper_after_the_timing_tree(schema):
    """The negative control: `CT_Slide` orders the transition before the timing, and a branch
    keeps the place its wrapper had."""
    root = _morph_slide()
    wrapper = root.find(f"{{{_MC}}}AlternateContent")
    root.remove(wrapper)
    root.append(wrapper)

    assert not schema.validate(_branch(root, "Fallback"))
    assert "transition" in schema.error_log[0].message


def test_the_vendored_schema_is_present():
    """A skipped schema gate proves nothing; this fails rather than skips."""
    assert SCHEMA.is_file(), f"missing vendored schema at {SCHEMA}"


def test_a_click_build_validates(schema):
    prs, slide, text, blank, chart = _deck()
    add_click_build(slide, [text, blank])
    assert _validate(schema, prs) == []


def test_a_staggered_click_build_validates(schema):
    prs, slide, text, blank, chart = _deck()
    add_click_build(slide, [text, blank], 80)
    assert _validate(schema, prs) == []


@pytest.mark.parametrize("kind", ["fade", "wipeup", "wiperight"])
def test_every_click_sequence_effect_kind_validates(schema, kind):
    prs, slide, text, blank, chart = _deck()
    add_click_sequence(slide, [[(text, kind)], [(blank, kind)]], 60)
    assert _validate(schema, prs) == []


@pytest.mark.parametrize("kind", ["fade", "wipeup", "wiperight"])
@pytest.mark.parametrize("by", ["category", "series", "element", "all"])
def test_every_chart_build_validates(schema, by, kind):
    """`bldStep` is required on `<a:chart>`. Every
    entrance a theme's `datum` role may bind is built the same way."""
    prs, slide, text, blank, chart = _deck()
    add_chart_build(slide, chart, by, parts=3, kind=kind)
    assert _validate(schema, prs) == []


@pytest.mark.parametrize("kind", ["fade", "wipeup", "wiperight"])
def test_every_after_previous_chain_validates(schema, kind):
    """`afterEffect` group starts and their beat gate, the auto-advance path."""
    prs, slide, text, blank, chart = _deck()
    add_click_sequence(slide, [[(text, kind)], [(blank, kind)]], beat_ms=250)
    assert _validate(schema, prs) == []


def test_a_build_over_only_text_free_shapes_validates(schema):
    """No bldP is legal for these, so the build list is omitted — and `<p:bldLst/>`
    with no children would be invalid."""
    prs, slide, text, blank, chart = _deck()
    add_click_build(slide, [blank])
    assert _validate(schema, prs) == []


def test_a_group_holding_both_shape_kinds_validates(schema):
    """A worded shape and a text-free one on one click: the first entrance node carries `grpId` and
    the second does not. The XSD accepts either — it is `use="optional"` on
    `CT_TLCommonTimeNodeData` — so this gates only spelling and position;
    `tests/test_pptx_helpers.py` gates which node."""
    prs, slide, text, blank, chart = _deck()
    add_click_sequence(slide, [[text, blank]])
    assert _validate(schema, prs) == []


def test_an_interactive_reveal_validates(schema):
    prs, slide, text, blank, chart = _deck()
    add_click_reveals(slide, [(text, blank)])
    assert _validate(schema, prs) == []


def test_two_triggers_onto_one_target_stay_siblings_under_the_root(schema):
    """Every shape a trigger placement drew listens, so a two-shape trigger writes two `<p:seq>`.
    Both hang off the tmRoot: burying the second inside the first validates, but it would only arm
    once the outer sequence had run."""
    prs, slide, text, blank, chart = _deck()
    add_click_reveals(slide, [(text, blank), (chart, blank)])

    assert _validate(schema, prs) == []
    seqs = list(etree.fromstring(_slide_xml(prs)).iter(f"{{{_PML}}}seq"))
    assert len(seqs) == 2
    assert {s.getparent().getparent().get("nodeType") for s in seqs} == {"tmRoot"}


# PowerPoint for Mac 16's own trigger, saved onto the confirmation kit's deck 04: ids dropped,
# trigger spid `T`, target spid `R`, and without the `grpId`/`bldP` it adds for a worded target.
_POWERPOINT_TRIGGER = (
    f'<p:seq xmlns:p="{_PML}" concurrent="1" nextAc="seek">'
    '<p:cTn restart="whenNotActive" fill="hold" evtFilter="cancelBubble" nodeType="interactiveSeq">'
    '<p:stCondLst><p:cond evt="onClick" delay="0"><p:tgtEl><p:spTgt spid="T"/></p:tgtEl></p:cond></p:stCondLst>'
    '<p:endSync evt="end" delay="0"><p:rtn val="all"/></p:endSync>'
    '<p:childTnLst><p:par><p:cTn fill="hold"><p:stCondLst><p:cond delay="0"/></p:stCondLst><p:childTnLst>'
    '<p:par><p:cTn fill="hold"><p:stCondLst><p:cond delay="0"/></p:stCondLst><p:childTnLst>'
    '<p:par><p:cTn presetID="1" presetClass="entr" presetSubtype="0" fill="hold" nodeType="clickEffect">'
    '<p:stCondLst><p:cond delay="0"/></p:stCondLst><p:childTnLst><p:set><p:cBhvr>'
    '<p:cTn dur="1" fill="hold"><p:stCondLst><p:cond delay="0"/></p:stCondLst></p:cTn>'
    '<p:tgtEl><p:spTgt spid="R"/></p:tgtEl>'
    "<p:attrNameLst><p:attrName>style.visibility</p:attrName></p:attrNameLst>"
    '</p:cBhvr><p:to><p:strVal val="visible"/></p:to></p:set></p:childTnLst></p:cTn></p:par>'
    "</p:childTnLst></p:cTn></p:par></p:childTnLst></p:cTn></p:par></p:childTnLst></p:cTn>"
    '<p:nextCondLst><p:cond evt="onClick" delay="0"><p:tgtEl><p:spTgt spid="T"/></p:tgtEl></p:cond></p:nextCondLst>'
    "</p:seq>"
)


def _skeleton(node, spids: dict[str, str]) -> list[tuple[str, tuple[tuple[str, str], ...], str]]:
    """Every element under ``node`` in document order as (tag, attributes, text), with ``id``
    dropped and each ``spid`` renamed through ``spids``."""
    out = []
    for el in node.iter():
        attrs = tuple(
            sorted(
                (k, spids.get(v, v) if k == "spid" else v)
                for k, v in el.attrib.items()
                if k != "id"
            )
        )
        out.append((etree.QName(el).localname, attrs, (el.text or "").strip()))
    return out


def test_a_trigger_is_shaped_like_powerpoints_own(schema):
    """`cancelBubble`, an `endSync`, a next-condition on the trigger's own click and no
    previous-condition: a click anywhere else on the slide advances it instead of stepping
    every trigger forward. The shape is PowerPoint's, learned back from its save."""
    prs, slide, text, blank, chart = _deck()
    add_click_reveals(slide, [(text, blank)])

    assert _validate(schema, prs) == []
    seq = etree.fromstring(_slide_xml(prs)).find(f".//{{{_PML}}}seq")
    expected = etree.fromstring(_POWERPOINT_TRIGGER.encode())
    assert _skeleton(seq, {str(text): "T", str(blank): "R"}) == _skeleton(expected, {})


def test_the_gate_catches_an_end_sync_out_of_order(schema):
    """The negative control for the case above: `endSync` after `childTnLst` breaks
    `CT_TLCommonTimeNodeData`'s sequence, which LibreOffice repairs without a word."""
    prs, slide, text, blank, chart = _deck()
    add_click_reveals(slide, [(text, blank)])
    root = etree.fromstring(_slide_xml(prs))
    ctn = root.find(f".//{{{_PML}}}seq/{{{_PML}}}cTn")
    sync = ctn.find(f"{{{_PML}}}endSync")
    ctn.remove(sync)
    ctn.append(sync)

    assert not schema.validate(root)
    assert "endSync" in schema.error_log[0].message


@pytest.mark.parametrize("kind", sorted(EFFECTS))
def test_every_transition_validates(schema, kind):
    prs, slide, text, blank, chart = _deck()
    add_transition(slide, kind)
    assert _validate(schema, prs) == []


@pytest.mark.parametrize(
    "kind, direction",
    [(k, d) for k, dirs in sorted(EFFECTS.items()) for d in dirs],
)
def test_every_transition_direction_validates(schema, kind, direction):
    """Direction vocabularies are per element — a shared list is invalid at `strips`."""
    prs, slide, text, blank, chart = _deck()
    add_transition(slide, kind, direction=direction)
    assert _validate(schema, prs) == []


@pytest.mark.parametrize("speed", SPEEDS)
def test_every_transition_speed_validates(schema, speed):
    prs, slide, text, blank, chart = _deck()
    add_transition(slide, "wipe", speed=speed)
    assert _validate(schema, prs) == []


def test_a_transition_beside_an_animation_validates_and_keeps_child_order(schema):
    """`CT_Slide` is an xsd:sequence. LibreOffice repairs a wrong order on import, so
    this is the only mechanical check that the two writers do not collide."""
    prs, slide, text, blank, chart = _deck()
    add_click_sequence(slide, [[text], [blank]])
    add_transition(slide, "push", direction="u")

    assert _validate(schema, prs) == []
    tags = [el.tag.split("}")[1] for el in slide._element]
    assert tags.index("transition") < tags.index("timing")


def test_the_gate_catches_a_missing_required_attribute(schema):
    """The negative control. Without it, a validator that silently passed everything
    would look identical to one that works."""
    prs, slide, text, blank, chart = _deck()
    add_chart_build(slide, chart, "category", parts=3)
    sabotaged = re.sub(rb' bldStep="[^"]+"', b"", _slide_xml(prs))

    assert not schema.validate(etree.fromstring(sabotaged))
    assert "bldStep" in schema.error_log[0].message


def test_a_click_sequence_revealing_paragraphs_of_one_shape_validates(schema):
    """`one_at_a_time` on a single bullets column reveals one paragraph per click."""
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    box = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(3), Inches(2))
    box.text_frame.text = "one"
    for line in ("two", "three"):
        box.text_frame.add_paragraph().text = line
    add_click_sequence(slide, [[(box.shape_id, "fade", i)] for i in range(3)])
    assert _validate(schema, prs) == []


def test_alt_text_and_the_decorative_flag_validate_on_every_figure_kind(schema):
    """`descr` on each non-visual block, and the decorative extension inside `cNvPr`'s
    `a:extLst`, which the schema types as a closed sequence ending in that list."""
    from deckwright.utils.a11y import describe

    prs, slide, text, blank, chart = _deck()
    shapes = {s.shape_id: s for s in slide.shapes}
    describe(shapes[chart], alt="A chart")
    describe(shapes[text], decorative=True)
    describe(shapes[blank], alt="A box")
    assert _validate(schema, prs) == []


def test_the_gate_catches_the_decorative_list_out_of_order(schema):
    """The negative control for the case above: a click action after `a:extLst` breaks the
    sequence, so an extension written in the wrong place would not pass."""
    from deckwright.utils.a11y import describe

    prs, slide, text, blank, chart = _deck()
    describe(next(s for s in slide.shapes if s.shape_id == text), decorative=True)
    sabotaged = _slide_xml(prs).replace(b"</a:extLst>", b'</a:extLst><a:hlinkClick r:id=""/>')

    assert not schema.validate(etree.fromstring(sabotaged))
    assert "hlinkClick" in schema.error_log[0].message


def test_a_click_action_beside_the_decorative_flag_validates_in_order(schema):
    """`goto:` writes `a:hlinkClick` into a `cNvPr` whose `a:extLst` alt text may already
    hold; the sequence puts the click first whichever was written first."""
    from deckwright.compile.goto import write_gotos
    from deckwright.utils.a11y import describe

    prs, slide, text, blank, chart = _deck()
    second = prs.slides.add_slide(prs.slide_layouts[6])
    shapes = {s.shape_id: s for s in slide.shapes}
    describe(shapes[text], decorative=True)
    write_gotos(
        [(shapes[text], "next"), (shapes[blank], "back"), (shapes[chart], "back")],
        slides={"back": second},
    )
    assert _validate(schema, prs) == []
    tags = [el.tag.split("}")[1] for el in shapes[text]._element.nvSpPr.cNvPr]
    assert tags == ["hlinkClick", "extLst"]


def test_a_link_run_with_its_colour_extension_validates(schema):
    """`a:hlinkClick` sits after the run's fill and face in `a:rPr`, and carries the
    hyperlink-colour extension in its own `a:extLst`."""
    from deckwright.utils.shapes import para
    from pptx.dml.color import RGBColor

    prs, slide, text, blank, chart = _deck()
    frame = next(s for s in slide.shapes if s.shape_id == blank).text_frame
    para(frame, "Read [the guide](https://example.com/g) first", 18, RGBColor(0, 0, 0), first=True)
    assert _validate(schema, prs) == []


def test_a_cjk_run_marked_with_its_language_and_face_validates(schema):
    from deckwright.compile.eastasian import mark_east_asian

    prs, slide, text, blank, chart = _deck()
    frame = next(s for s in slide.shapes if s.shape_id == blank).text_frame
    run = frame.paragraphs[0].add_run()
    run.text = "売上は伸びました"
    run.font.name = "Helvetica"
    run.hyperlink.address = "https://example.com"
    mark_east_asian(slide, ea={"ja": "Hiragino Sans"}, lang=None, where="s")
    assert _validate(schema, prs) == []


_MATH_SCHEMA = SCHEMA.parent / "shared-math.xsd"
# wml.xsd names ../mce/mc.xsd for one attribute; this is that attribute, and nothing more.
_IGNORABLE = (
    b'<xsd:schema xmlns:xsd="http://www.w3.org/2001/XMLSchema" '
    b'targetNamespace="http://schemas.openxmlformats.org/markup-compatibility/2006">'
    b'<xsd:attribute name="Ignorable" type="xsd:string"/></xsd:schema>'
)


class _Ignorable(etree.Resolver):
    def resolve(self, url, pubid, context):
        if url.endswith("mce/mc.xsd"):
            return self.resolve_string(_IGNORABLE, context)
        return None


@pytest.fixture(scope="module")
def math_schema():
    parser = etree.XMLParser(no_network=True)
    parser.resolvers.add(_Ignorable())
    return etree.XMLSchema(etree.parse(str(_MATH_SCHEMA), parser))


_EVERY_NODE = (
    r"\left( \sum_{i=1}^{n} x_i^2 \right) + \sqrt[3]{\frac{a}{b}} - \lim_{x \to 0} y_j"
    r" + \int_0^1 z^2 + \prod w + \sqrt{q} + \text{if } p \leq \infty"
)


def _math(tex: str):
    """The `m:oMathPara` an equation writes, less the DrawingML run properties PowerPoint
    keeps where the ISO schema has Word's: those are DrawingML's to validate, not Office
    Math's."""
    from deckwright.components._omml import omml
    from deckwright.components._tex import parse

    root = etree.fromstring(omml(parse(tex, where="t"), size_pt=24, ink="1A1D21").encode())
    for props in list(root.iter(f"{{{_DML}}}rPr")):
        props.getparent().remove(props)
    return root.find(f"{{{_OMML}}}oMathPara")


def test_every_node_an_equation_writes_is_valid_office_math(math_schema):
    assert math_schema.validate(_math(_EVERY_NODE)), [e.message for e in math_schema.error_log]


def test_the_math_gate_catches_a_fraction_written_upside_down(math_schema):
    """The negative control: `CT_F` is `num` then `den`."""
    para = _math(_EVERY_NODE)
    fraction = para.find(f".//{{{_OMML}}}f")
    num, den = fraction.find(f"{{{_OMML}}}num"), fraction.find(f"{{{_OMML}}}den")
    fraction.remove(num)
    fraction.append(num)

    assert den is not None
    assert not math_schema.validate(para)
    assert "num" in math_schema.error_log[0].message


@pytest.mark.parametrize("which", ["Choice", "Fallback"])
def test_a_slide_carrying_an_equation_validates_in_each_branch(
    schema, math_schema, which, ctx_factory
):
    """The component wraps the whole shape, so each reader sees a complete, valid slide."""
    from deckwright.layouts.components import get_component

    ctx = ctx_factory({"equation": {"tex": r"x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}"}})
    get_component("equation")(ctx)
    root = etree.fromstring(etree.tostring(ctx.slide._element))

    assert schema.validate(_branch(root, which)), [e.message for e in schema.error_log]
    if which == "Choice":
        (para,) = root.iter(f"{{{_OMML}}}oMathPara")
        for props in list(para.iter(f"{{{_DML}}}rPr")):
            props.getparent().remove(props)
        assert math_schema.validate(para), [e.message for e in math_schema.error_log]
