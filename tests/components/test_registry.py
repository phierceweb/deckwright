import pytest

from deckwright.errors import LayoutError
from deckwright.layouts.components import component, get_component, registered_components


def test_a_registered_component_is_retrievable():
    @component("c-basic")
    def _basic(ctx):
        return []

    assert get_component("c-basic") is _basic
    assert "c-basic" in registered_components()


def test_unknown_component_lists_what_is_available():
    @component("c-known")
    def _known(ctx):
        return []

    with pytest.raises(LayoutError, match=r"unknown body component 'nope'.*available:.*c-known"):
        get_component("nope")


def test_duplicate_registration_is_rejected():
    @component("c-dupe")
    def _one(ctx):
        return []

    with pytest.raises(LayoutError, match="already registered"):

        @component("c-dupe")
        def _two(ctx):
            return []


def test_registered_components_are_sorted():
    for name in ("c-zeta", "c-alpha"):
        component(name)(lambda ctx: [])
    names = registered_components()
    assert list(names) == sorted(names)


def test_the_registry_is_isolated_between_tests():
    assert "c-basic" not in registered_components()
