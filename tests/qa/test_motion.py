"""What the timing says. Every other check reads a slide's final frame; LibreOffice draws
only that frame, so these are the only checks that can see the order information arrives."""

from __future__ import annotations

import re
import shutil
import zipfile

import pytest

from deckwright.qa.model import Severity
from deckwright.qa.motion import check_beats, check_triggers


def _manifest(*animations):
    return {"slides": [{"index": 1, "animations": list(animations)}]}


def test_a_together_build_is_reported_as_one_click(theme):
    """The defect this check exists on top of: `animate: together` fades every group onto
    one click, and the manifest used to record one step per group."""
    found = check_beats(
        _manifest({"kind": "click_build", "clicks": 1, "steps": [[f"s{i}" for i in range(8)]]}),
        theme,
    )
    assert [f.check for f in found] == ["beats"]
    assert found[0].severity is Severity.INFO
    assert "1 click reveals 8 shape(s)" in found[0].detail


def test_a_staged_build_reports_its_beat_sizes(theme):
    found = check_beats(
        _manifest({"kind": "click_sequence", "clicks": 3, "steps": [["a"], ["b", "c"], ["d"]]}),
        theme,
    )
    assert "3 click(s), 4 shapes, beats of 1, 2, 1" in found[0].detail


def test_an_after_previous_chain_is_one_click_not_one_per_beat(theme):
    """`motion.advance: after_previous` chains every beat onto a single advance, so a beat
    count read as a click count overstates what the presenter does."""
    found = check_beats(
        _manifest({"kind": "click_sequence", "clicks": 1, "steps": [["a"], ["b"], ["c"]]}), theme
    )
    assert "1 click, 3 beats chained by 'motion.advance: after_previous'" in found[0].detail


def test_an_interactive_reveal_spends_no_slide_advance(theme):
    found = check_beats(
        _manifest({"kind": "click_reveals", "clicks": 0, "steps": [["a", "b"]], "trigger": "q"}),
        theme,
    )
    assert "no slide advance; one trigger reveals 2 shape(s)" in found[0].detail


def test_a_chart_build_names_its_axes_click(theme):
    found = check_beats(_manifest({"kind": "chart_build", "clicks": 5, "steps": [["f"]]}), theme)
    assert "5 click(s): the chart's axes, then one per part" in found[0].detail


def test_a_staged_beat_over_the_ceiling_is_flagged(theme):
    """Issue 12's literal example: a single click revealing eleven shapes, on a slide that
    asked to be staged."""
    found = check_beats(
        _manifest(
            {"kind": "click_sequence", "clicks": 2, "steps": [["a"], [f"s{i}" for i in range(11)]]}
        ),
        theme,
    )
    flagged = [f for f in found if f.check == "beat-size"]
    assert len(flagged) == 1
    assert flagged[0].severity is Severity.WARN
    assert "beat 2 of 2 reveals 11 shapes at once" in flagged[0].detail


def test_a_together_build_is_never_flagged_for_beat_size(theme):
    """`animate: together` *is* the instruction "everything on one click". Flagging it
    contradicts a declaration, the way flagging a `bleed: true` shape would."""
    found = check_beats(
        _manifest({"kind": "click_build", "clicks": 1, "steps": [[f"s{i}" for i in range(20)]]}),
        theme,
    )
    assert [f for f in found if f.check == "beat-size"] == []


def test_a_trigger_reveal_is_never_flagged_for_beat_size(theme):
    """`reveals:` spends no slide advance and records every revealed shape as one step,
    so its "beat" is a shape count. Flagging it tells a correct slide to split the
    placement or say `animate: together` — a spec the compiler refuses on that slide."""
    found = check_beats(
        _manifest(
            {
                "kind": "click_reveals",
                "clicks": 0,
                "steps": [[f"s{i}" for i in range(11)]],
                "trigger": "q",
            }
        ),
        theme,
    )
    assert [f for f in found if f.check == "beat-size"] == []
    assert [f for f in found if f.check == "beats"], "the rhythm line is still reported"


def test_the_beat_ceiling_is_operational(theme, monkeypatch):
    steps = [["a"], ["b", "c", "d"]]
    anim = _manifest({"kind": "click_sequence", "clicks": 2, "steps": steps})
    assert [f for f in check_beats(anim, theme) if f.check == "beat-size"] == []
    monkeypatch.setenv("DECKWRIGHT_MAX_BEAT_SHAPES", "2")
    assert len([f for f in check_beats(anim, theme) if f.check == "beat-size"]) == 1


def test_a_nonsense_ceiling_falls_back_to_the_default(theme, monkeypatch):
    """A zero would make the check fire on every beat; a check nobody can silence is a
    check that gets ignored."""
    monkeypatch.setenv("DECKWRIGHT_MAX_BEAT_SHAPES", "0")
    anim = _manifest({"kind": "click_sequence", "clicks": 1, "steps": [["a", "b"]]})
    assert [f for f in check_beats(anim, theme) if f.check == "beat-size"] == []


# --- reveals that cannot fire -------------------------------------------------

_P = "http://schemas.openxmlformats.org/presentationml/2006/main"


def _rewritten(source, tmp_path, name, edit):
    """A copy of ``source`` whose slide1 timing has been hand-edited."""
    dest = tmp_path / name
    shutil.copy(source, dest)
    with zipfile.ZipFile(dest) as z:
        parts = {n: z.read(n) for n in z.namelist()}
    parts["ppt/slides/slide1.xml"] = edit(parts["ppt/slides/slide1.xml"].decode()).encode()
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
        for n, data in parts.items():
            z.writestr(n, data)
    return dest


@pytest.fixture
def revealing(tmp_path, theme_file):
    """A built deck where clicking one card reveals another."""
    from deckwright.compile.build import build_deck

    spec = tmp_path / "rev.deck.yaml"
    spec.write_text(
        "theme: testtheme\ntitle: T\nout: out/Rev.pptx\n---\n"
        "title: Click the question\n"
        "place:\n"
        "  - at: {cols: left-half, rows: {from: 1, to: 6}}\n"
        "    id: q\n"
        "    card: {heading: The question, body: What went wrong}\n"
        "  - at: {cols: right-half, rows: {from: 1, to: 6}}\n"
        "    reveals: q\n"
        "    card: {heading: The answer, body: One bug.}\n"
    )
    build_deck(spec, theme_path=theme_file)
    return tmp_path / "out" / "Rev.pptx"


def test_a_deck_the_compiler_built_has_no_dead_trigger(revealing):
    """The compiler refuses every spec-level case — self-reveal, an unknown id, a ring, an
    end that drew nothing — so this check is a guard on hand-edits and drift, like
    `animation-target` and `stale-manifest` beside it."""
    assert [f for f in check_triggers(revealing) if f.check == "dead-trigger"] == []


def test_a_trigger_hidden_by_its_own_target_can_never_fire(revealing, tmp_path):
    """A hand-edit that points every reveal back at a shape the reveal itself hides: none of
    them can be clicked to show the others. The package is valid OOXML and the render — which
    draws the final frame — is identical either way."""

    def ring(xml):
        head, _, timing = xml.partition("<p:timing")
        hidden = re.findall(r'nodeType="clickEffect".*?<p:spTgt spid="(\d+)"/>', timing, re.S)
        rewritten = re.sub(
            r'(<p:cond evt="onClick" delay="0"><p:tgtEl><p:spTgt spid=")\d+(")',
            lambda m, it=iter(hidden): m.group(1) + next(it) + m.group(2),
            "<p:timing" + timing,
        )
        return head + rewritten

    deck = _rewritten(revealing, tmp_path, "ring.pptx", ring)
    dead = [f for f in check_triggers(deck) if f.severity is Severity.ERROR]
    assert dead, "a ring of hidden triggers reported nothing"
    assert all("can never be shown" in f.detail for f in dead)


def test_a_target_the_main_build_also_reveals_is_already_on_screen(revealing, tmp_path):
    """The click does nothing a viewer can see: the shape arrived with the main build."""

    def add_main(xml):
        target = re.search(r'nodeType="clickEffect".*?<p:spTgt spid="(\d+)"/>', xml, re.S).group(1)
        main = (
            f'<p:seq concurrent="1" nextAc="seek"><p:cTn id="900" nodeType="mainSeq">'
            f'<p:childTnLst><p:par><p:cTn id="901" presetClass="entr" nodeType="clickEffect">'
            f'<p:childTnLst><p:set><p:cBhvr><p:cTn id="902" dur="1"/>'
            f'<p:tgtEl><p:spTgt spid="{target}"/></p:tgtEl>'
            f"<p:attrNameLst><p:attrName>style.visibility</p:attrName></p:attrNameLst>"
            f'</p:cBhvr><p:to><p:strVal val="visible"/></p:to></p:set>'
            f"</p:childTnLst></p:cTn></p:par></p:childTnLst></p:cTn></p:seq>"
        )
        tail = "</p:childTnLst></p:cTn></p:par></p:tnLst></p:timing>"
        assert tail in xml
        return xml.replace(tail, main + tail, 1)

    deck = _rewritten(revealing, tmp_path, "double.pptx", add_main)
    warned = [f for f in check_triggers(deck) if f.severity is Severity.WARN]
    assert warned, "a target the main build also reveals reported nothing"
    assert all("already on screen" in f.detail for f in warned)
    # The plate and its words are both revealed, so every warning names the same target.
    assert len({f.detail.split(" is revealed")[0] for f in warned}) == 1
