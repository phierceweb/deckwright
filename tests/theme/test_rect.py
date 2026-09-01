from deckwright.theme.model import Rect


def test_rect_exposes_its_edges():
    r = Rect(1.0, 2.0, 3.0, 4.0)
    assert (r.right, r.bottom) == (4.0, 6.0)


def test_rect_inset_shrinks_on_both_axes():
    assert Rect(1.0, 2.0, 6.0, 8.0).inset(0.5, 1.0) == Rect(1.5, 3.0, 5.0, 6.0)
