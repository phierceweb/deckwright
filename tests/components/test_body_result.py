import dataclasses

import pytest

from deckwright.layouts.components import BodyResult, as_body_result


def test_a_bare_group_list_normalises():
    result = as_body_result([[2], [3]])
    assert result.groups == [[2], [3]]
    assert result.height is None


def test_a_body_result_passes_through():
    original = BodyResult(groups=[[2]], height=1.5)
    assert as_body_result(original) is original


def test_none_normalises_to_empty():
    assert as_body_result(None) == BodyResult(groups=[], height=None)


def test_groups_may_carry_reveal_kinds():
    result = as_body_result([[(2, "wipeup"), 3]])
    assert result.groups == [[(2, "wipeup"), 3]]


def test_body_result_is_frozen():
    with pytest.raises(dataclasses.FrozenInstanceError):
        BodyResult(groups=[], height=None).height = 2.0


def test_height_defaults_to_none():
    assert BodyResult(groups=[[2]]).height is None
