"""The beats view: a build's reveal order as words.

`.content.md`'s sibling. Both are derived from the same `to_dict()`, so neither can
disagree with the manifest — what these check is that a reader learns the right thing.
"""

from __future__ import annotations

from deckwright.compile.beats import render_beats


def _slide(index, animations, shapes=(), title=None):
    named = list(shapes)
    if title:
        named.insert(0, {"name": f"s{index}.chrome.title", "lines": [title]})
    return {"index": index, "animations": animations, "shapes": named}


def test_a_deck_that_does_not_animate_says_so():
    out = render_beats({"deck": "d.pptx", "slides": [{"index": 1}]})
    assert "Nothing on this deck animates." in out


def test_a_slide_is_headed_by_its_title_not_only_its_index():
    """A count of animated slides reports no change when an animation moves to a different
    slide. Keying the section to the title is what makes that visible in a diff."""
    out = render_beats(
        {
            "deck": "d.pptx",
            "slides": [
                _slide(
                    4,
                    [{"kind": "click_sequence", "clicks": 1, "steps": [["s4.p1.card#1"]]}],
                    title="It was one bug, not a bad launch",
                )
            ],
        }
    )
    assert "## Slide 4 · It was one bug, not a bad launch" in out


def test_a_beat_reads_back_the_words_that_arrive_in_it():
    out = render_beats(
        {
            "deck": "d.pptx",
            "slides": [
                _slide(
                    1,
                    [
                        {
                            "kind": "click_sequence",
                            "clicks": 2,
                            "steps": [["s1.p1.callouts#1"], ["s1.p1.callouts#2"]],
                        }
                    ],
                    shapes=[
                        {"name": "s1.p1.callouts#1", "lines": ["The turn"]},
                        {"name": "s1.p1.callouts#2", "lines": ["The cost"]},
                    ],
                )
            ],
        }
    )
    assert "1. The turn" in out
    assert "2. The cost" in out


def test_the_click_total_counts_clicks_not_beats():
    """`animate: together` spends one click however many groups its components returned,
    and an interactive reveal spends none. Summing steps overstates both."""
    out = render_beats(
        {
            "deck": "d.pptx",
            "slides": [
                _slide(1, [{"kind": "click_build", "clicks": 1, "steps": [["a", "b", "c", "d"]]}]),
                _slide(
                    2,
                    [{"kind": "click_reveals", "clicks": 0, "steps": [["x"]], "trigger": "q"}],
                ),
            ],
        }
    )
    assert "2 of 2 slide(s) animate · 1 click(s) · 1 interactive trigger(s)" in out


def test_a_trigger_is_named_by_its_words_not_by_the_shape_that_carries_them():
    """A card's plate is drawn first and says nothing, so `click **s1.q.card#1**` would
    tell a reader nothing about which card to click."""
    out = render_beats(
        {
            "deck": "d.pptx",
            "slides": [
                _slide(
                    1,
                    [
                        {
                            "kind": "click_reveals",
                            "clicks": 0,
                            "steps": [["s1.a.card#2"]],
                            "trigger": "s1.q.card#1",
                        }
                    ],
                    shapes=[
                        {"name": "s1.q.card#1"},
                        {"name": "s1.q.card#2", "lines": ["What broke?"]},
                        {"name": "s1.a.card#2", "lines": ["The cache key"]},
                    ],
                )
            ],
        }
    )
    assert "- click **What broke?** → The cache key" in out


def test_a_chart_build_names_its_axes_click_rather_than_one_shape():
    """The manifest records the frame, once. What the audience sees is the axes and then
    one part per click, and a reader counting shapes would read it as a single reveal."""
    out = render_beats(
        {
            "deck": "d.pptx",
            "slides": [
                _slide(1, [{"kind": "chart_build", "clicks": 4, "steps": [["s1.p1.chart"]]}])
            ],
        }
    )
    assert "1. the chart's axes and gridlines" in out
    assert out.count("one of the chart's parts") == 3


def test_a_beat_that_carries_no_words_names_its_shapes_instead():
    """A `rule` or an `icon` says nothing. An empty bullet would read as a beat that
    reveals nothing at all."""
    out = render_beats(
        {
            "deck": "d.pptx",
            "slides": [
                _slide(1, [{"kind": "click_sequence", "clicks": 1, "steps": [["s1.p1.rule#1"]]}])
            ],
        }
    )
    assert "*(1 shape(s), no words: s1.p1.rule#1)*" in out


def test_a_manifest_written_before_clicks_were_recorded_still_renders():
    """An older manifest read one beat as one click, which is what it meant then."""
    out = render_beats(
        {
            "deck": "d.pptx",
            "slides": [_slide(1, [{"kind": "click_sequence", "steps": [["a"], ["b"]]}])],
        }
    )
    assert "2 click(s)" in out
