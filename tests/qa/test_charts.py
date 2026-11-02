"""What a deck's chart parts say about the charts: a claim the render cannot verify, and a
chart too thin for the treatment it was given. Every case is a real saved deck."""

from __future__ import annotations

import pathlib
import re

from pptx import Presentation
from pptx.enum.chart import XL_CHART_TYPE
from pptx.util import Inches

from deckwright.qa.charts import check_charts
from deckwright.qa.model import Severity


def _charted(tmp_path, chart_type, values, name="c.pptx", *, categories=("Up", "Down")):
    """A saved deck holding one chart of ``chart_type``."""
    from pptx.chart.data import CategoryChartData

    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    data = CategoryChartData()
    data.categories = list(categories)
    data.add_series("s", values)
    slide.shapes.add_chart(chart_type, Inches(1), Inches(1), Inches(6), Inches(4), data)
    path = tmp_path / name
    prs.save(str(path))
    return path


# --- charts the render cannot verify ----------------------------------------


def test_a_bar_chart_with_a_negative_value_is_flagged_unverifiable(tmp_path):
    """The file is correct; the render this suite and `deckwright render` both go through plots the
    absolute value, so nothing automated can check the chart. Reproduced with bare python-pptx."""
    deck = _charted(tmp_path, XL_CHART_TYPE.COLUMN_CLUSTERED, (271, -146))
    findings = [f for f in check_charts(deck) if f.check == "chart-negative"]
    assert len(findings) == 1
    assert findings[0].severity is Severity.WARN
    assert findings[0].slide == 1
    assert "diverge" in findings[0].detail


def test_an_all_positive_bar_chart_is_clean(tmp_path):
    deck = _charted(tmp_path, XL_CHART_TYPE.COLUMN_CLUSTERED, (271, 146))
    assert [f for f in check_charts(deck) if f.check == "chart-negative"] == []


def test_a_line_chart_with_a_negative_value_is_not_flagged(tmp_path):
    """Line series render their negatives correctly, so warning about them is noise."""
    deck = _charted(tmp_path, XL_CHART_TYPE.LINE, (271, -146))
    assert [f for f in check_charts(deck) if f.check == "chart-negative"] == []


# --- charts too thin for the treatment they were given -----------------------


def test_a_two_bar_chart_is_flagged_and_the_finding_quotes_the_rule(tmp_path):
    """The class of slide both blind judges flagged, in two separate runs: a two-bar chart
    under a headline that already states both numbers."""
    deck = _charted(tmp_path, XL_CHART_TYPE.COLUMN_CLUSTERED, (36, 64))
    findings = [f for f in check_charts(deck) if f.check == "chart-datapoints"]
    assert len(findings) == 1
    assert findings[0].severity is Severity.WARN
    assert findings[0].slide == 1
    assert "plots 2 datapoints" in findings[0].detail


def test_the_quoted_rule_is_the_sentence_choosing_md_carries(tmp_path):
    """The finding quotes the doc. Reword one side only and it quotes nothing — worse than a
    paraphrase, because it still reads as sourced."""
    choosing = (pathlib.Path(__file__).resolve().parents[2] / "docs/choosing.md").read_text(
        encoding="utf-8"
    )
    deck = _charted(tmp_path, XL_CHART_TYPE.COLUMN_CLUSTERED, (36, 64))
    detail = next(f for f in check_charts(deck) if f.check == "chart-datapoints").detail
    quoted = re.search(r'"(A chart with[^"]+)"', detail)
    assert quoted is not None, detail
    assert quoted.group(1) in choosing


def test_a_four_bar_chart_is_not_flagged(tmp_path):
    """Four is the floor the rule states, so four passes it."""
    deck = _charted(
        tmp_path,
        XL_CHART_TYPE.COLUMN_CLUSTERED,
        (18, 36, 52, 64),
        categories=("Remote", "Urban", "Suburban", "Rural"),
    )
    assert [f for f in check_charts(deck) if f.check == "chart-datapoints"] == []


def test_values_are_counted_across_series_not_bars_per_category(tmp_path):
    """Two categories against two series is four numbers, and reads as a comparison. Counting
    categories instead flags real charts deckwright's own feature tour builds."""
    from pptx.chart.data import CategoryChartData

    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    data = CategoryChartData()
    data.categories = ["Up", "Down"]
    data.add_series("before", (36, 64))
    data.add_series("after", (41, 59))
    slide.shapes.add_chart(
        XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(1), Inches(1), Inches(6), Inches(4), data
    )
    deck = tmp_path / "two.pptx"
    prs.save(str(deck))
    assert [f for f in check_charts(deck) if f.check == "chart-datapoints"] == []


def test_a_thin_line_chart_is_exempt(tmp_path):
    """A line's claim is the direction between ordered points, which no `stats` row can make."""
    deck = _charted(tmp_path, XL_CHART_TYPE.LINE, (36, 64))
    assert [f for f in check_charts(deck) if f.check == "chart-datapoints"] == []


def test_a_thin_pie_is_exempt(tmp_path):
    """The parts sum to the whole, so a slice count is the composition being described."""
    deck = _charted(tmp_path, XL_CHART_TYPE.PIE, (36, 64))
    assert [f for f in check_charts(deck) if f.check == "chart-datapoints"] == []


def test_an_unreadable_deck_is_not_this_checks_finding(tmp_path):
    """`package` reports it; a second finding for the same fault is noise."""
    bad = tmp_path / "bad.pptx"
    bad.write_bytes(b"not a zip")
    assert check_charts(bad) == []


def test_a_series_is_as_long_as_its_cache_says_or_its_points_number():
    from lxml import etree

    from deckwright.qa.charts import _series_length

    c = "http://schemas.openxmlformats.org/drawingml/2006/chart"
    cached = '<c:val><c:numRef><c:numCache><c:ptCount val="{}"/></c:numCache></c:numRef></c:val>'
    points = '<c:val><c:numLit><c:pt idx="0"/><c:pt idx="1"/></c:numLit></c:val>'
    lengths = [
        _series_length(etree.fromstring(f'<c:ser xmlns:c="{c}">{body}</c:ser>'))
        for body in ("", cached.format("many"), cached.format("7"), points)
    ]
    assert lengths == [0, 0, 7, 2]


def test_a_malformed_chart_part_is_skipped(tmp_path):
    import zipfile

    from pptx.enum.chart import XL_CHART_TYPE as kinds

    deck = _charted(tmp_path, kinds.BAR_CLUSTERED, (1, -2))
    broken = tmp_path / "broken.pptx"
    with zipfile.ZipFile(deck) as src, zipfile.ZipFile(broken, "w") as dst:
        for item in src.infolist():
            data = src.read(item.filename)
            if item.filename.startswith("ppt/charts/chart"):
                data = b"<c:chartSpace"
            dst.writestr(item, data)
    assert [f.check for f in check_charts(deck)] != []
    assert check_charts(broken) == []


def _five_series(tmp_path, theme_file):
    from deckwright.compile import build_deck

    spec = tmp_path / "five.deck.yaml"
    rows = "".join(
        f"        - {{category: {c}, values: {{s1: 1, s2: 2, s3: 3, s4: 4, s5: 5}}}}\n"
        for c in "abcd"
    )
    spec.write_text(
        "theme: testtheme\ntitle: T\nout: out/Five.pptx\n---\ntitle: Five\n"
        "place:\n  - at: {cols: full}\n    chart:\n      kind: column\n      data:\n" + rows
    )
    return build_deck(spec, theme_path=theme_file).deck


def _series_findings(deck):
    return [f for f in check_charts(deck) if f.check == "series-colour"]


def test_five_series_on_four_accents_report_the_fill_two_of_them_share(tmp_path, theme_file):
    """The palette cycles once the accents run out, so the fifth series is the first again."""
    found = _series_findings(_five_series(tmp_path, theme_file))
    assert [(f.slide, f.severity) for f in found] == [(1, Severity.WARN)]
    assert found[0].detail.startswith("series s1 and s5 share the fill ")
    assert "the theme's 4 accent(s) ran out" in found[0].detail


def test_four_series_on_four_accents_report_nothing(tmp_path, theme_file):
    from deckwright.compile import build_deck

    spec = tmp_path / "four.deck.yaml"
    rows = "".join(
        f"        - {{category: {c}, values: {{s1: 1, s2: 2, s3: 3, s4: 4}}}}\n" for c in "abcd"
    )
    spec.write_text(
        "theme: testtheme\ntitle: T\nout: out/Four.pptx\n---\ntitle: Four\n"
        "place:\n  - at: {cols: full}\n    chart:\n      kind: column\n      data:\n" + rows
    )
    assert _series_findings(build_deck(spec, theme_path=theme_file).deck) == []


def test_a_fill_given_as_a_scheme_reference_is_judged_by_the_colour_it_resolves_to(
    tmp_path, theme_file
):
    """A chart edited by hand names `accent1` rather than a hex; one the theme cannot resolve
    is passed over rather than guessed at."""
    import zipfile

    from lxml import etree

    a = "http://schemas.openxmlformats.org/drawingml/2006/main"
    c = "http://schemas.openxmlformats.org/drawingml/2006/chart"
    deck = _five_series(tmp_path, theme_file)
    edited = tmp_path / "scheme.pptx"
    with zipfile.ZipFile(deck) as src, zipfile.ZipFile(edited, "w") as dst:
        for item in src.infolist():
            data = src.read(item.filename)
            if item.filename.startswith("ppt/charts/chart"):
                root = etree.fromstring(data)
                for ser, ref in zip(
                    root.iter(f"{{{c}}}ser"),
                    ("accent1", "accent1", "nope", "nope", "nope"),
                    strict=True,
                ):
                    fill = ser.find(f"{{{c}}}spPr/{{{a}}}solidFill")
                    for child in list(fill):
                        fill.remove(child)
                    etree.SubElement(fill, f"{{{a}}}schemeClr", val=ref)
                data = etree.tostring(root)
            dst.writestr(item, data)
    found = _series_findings(edited)
    assert len(found) == 1
    assert found[0].detail.startswith("series s1 and s2 share the fill ")
