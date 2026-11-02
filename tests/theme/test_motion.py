"""The theme's ``motion:`` block — the brand's pacing, kept out of the deck spec. The composer's use
of ``stagger_ms`` is exercised end to end by the corpus; the two rejections live here."""

from __future__ import annotations

import pytest

from deckwright.errors import ThemeError
from deckwright.theme import load_theme

from tests.theme.test_load import BASE, _write


def test_a_theme_that_says_nothing_about_motion_does_not_stagger(tmp_path, synthetic_template):
    theme = load_theme(_write(tmp_path, synthetic_template, BASE))
    assert theme.motion.stagger_ms == 0


def test_stagger_ms_is_read_from_the_theme(tmp_path, synthetic_template):
    body = BASE + "    motion:\n      stagger_ms: 80\n"
    theme = load_theme(_write(tmp_path, synthetic_template, body))
    assert theme.motion.stagger_ms == 80


def test_an_unknown_motion_key_is_refused_by_name(tmp_path, synthetic_template):
    body = BASE + "    motion:\n      staggerms: 80\n"
    with pytest.raises(ThemeError, match="unknown motion key 'staggerms'"):
        load_theme(_write(tmp_path, synthetic_template, body))


def test_a_negative_stagger_is_refused(tmp_path, synthetic_template):
    """A negative delay schedules an item before the click that reveals it."""
    body = BASE + "    motion:\n      stagger_ms: -40\n"
    with pytest.raises(ThemeError, match="stagger_ms is -40"):
        load_theme(_write(tmp_path, synthetic_template, body))


def test_a_theme_with_no_transition_block_writes_no_transition(tmp_path, synthetic_template):
    theme = load_theme(_write(tmp_path, synthetic_template, BASE))
    assert theme.motion.transition.kind == "none"


def test_a_transition_is_read_from_the_theme(tmp_path, synthetic_template):
    body = BASE + "    motion:\n      transition: {kind: push, dir: u, speed: slow}\n"
    t = load_theme(_write(tmp_path, synthetic_template, body)).motion.transition
    assert (t.kind, t.direction, t.speed) == ("push", "u", "slow")


def test_a_bad_transition_fails_at_load_naming_the_theme(tmp_path, synthetic_template):
    """A build reaches slide 40 before it would otherwise notice."""
    body = BASE + "    motion:\n      transition: {kind: strips, dir: l}\n"
    with pytest.raises(ThemeError, match=r"t\.yaml:.*'strips' has no direction 'l'"):
        load_theme(_write(tmp_path, synthetic_template, body))


def test_an_unknown_transition_key_is_refused(tmp_path, synthetic_template):
    body = BASE + "    motion:\n      transition: {kind: fade, sped: slow}\n"
    with pytest.raises(ThemeError, match="unknown transition key 'sped'"):
        load_theme(_write(tmp_path, synthetic_template, body))


def test_the_default_roles_bind_a_line_to_a_wipe(tmp_path, synthetic_template):
    """`wiperight` had no path from any spec until roles existed."""
    theme = load_theme(_write(tmp_path, synthetic_template, BASE))
    assert theme.motion.roles["line"] == "wiperight"
    assert theme.motion.roles["text"] == "fade"


def test_a_theme_rebinds_one_role_and_keeps_the_rest(tmp_path, synthetic_template):
    body = BASE + "    motion:\n      roles:\n        line: {kind: fade}\n"
    roles = load_theme(_write(tmp_path, synthetic_template, body)).motion.roles
    assert roles["line"] == "fade"
    assert roles["datum"] == "wipeup"


def test_an_unknown_motion_role_is_refused(tmp_path, synthetic_template):
    body = BASE + "    motion:\n      roles:\n        squiggle: {kind: fade}\n"
    with pytest.raises(ThemeError, match="unknown motion role 'squiggle'"):
        load_theme(_write(tmp_path, synthetic_template, body))


def test_a_role_bound_to_an_unknown_entrance_is_refused(tmp_path, synthetic_template):
    body = BASE + "    motion:\n      roles:\n        line: {kind: explode}\n"
    with pytest.raises(ThemeError, match="unknown entrance 'explode'"):
        load_theme(_write(tmp_path, synthetic_template, body))


def test_advance_defaults_to_on_click(tmp_path, synthetic_template):
    theme = load_theme(_write(tmp_path, synthetic_template, BASE))
    assert (theme.motion.advance, theme.motion.beat_ms) == ("on_click", 400)


def test_after_previous_is_read_from_the_theme(tmp_path, synthetic_template):
    body = BASE + "    motion:\n      advance: after_previous\n      beat_ms: 250\n"
    m = load_theme(_write(tmp_path, synthetic_template, body)).motion
    assert (m.advance, m.beat_ms) == ("after_previous", 250)


def test_an_unknown_advance_is_refused(tmp_path, synthetic_template):
    body = BASE + "    motion:\n      advance: whenever\n"
    with pytest.raises(ThemeError, match="advance must be one of on_click, after_previous"):
        load_theme(_write(tmp_path, synthetic_template, body))
