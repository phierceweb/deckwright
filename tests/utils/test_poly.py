from deckwright.utils.poly import point_in_poly, poly_hits_box, poly_x_span, segments_cross

WEDGE = ((1.0, 0.7227), (1.0, 1.0), (0.8250, 1.0))
BAND = ((0.0, 0.0), (1.0, 0.0), (1.0, 0.1), (0.0, 0.1))


def test_a_point_inside_the_wedge_is_contained():
    assert point_in_poly(WEDGE, 0.98, 0.97) is True


def test_a_point_above_the_diagonal_is_outside():
    """The whole point of a polygon region: this corner-square point is usable."""
    assert point_in_poly(WEDGE, 0.86, 0.75) is False


def test_a_point_left_of_the_wedge_is_outside():
    assert point_in_poly(WEDGE, 0.45, 0.95) is False


def test_a_box_overlapping_the_wedge_hits_it():
    assert poly_hits_box(WEDGE, 0.93, 0.92, 0.06, 0.05) is True


def test_a_box_clear_of_the_wedge_does_not_hit_it():
    assert poly_hits_box(WEDGE, 0.05, 0.23, 0.45, 0.40) is False


def test_a_box_straddling_the_diagonal_hits_it():
    assert poly_hits_box(WEDGE, 0.885, 0.853, 0.075, 0.08) is True


def test_a_box_crossing_a_thin_band_without_a_shared_vertex_hits_it():
    """Edge-vs-edge crossing: neither shape has a vertex inside the other."""
    assert poly_hits_box(BAND, 0.375, -0.13, 0.075, 0.40) is True


def test_two_crossing_segments_are_detected():
    assert segments_cross((0.0, 0.0), (1.0, 1.0), (0.0, 1.0), (1.0, 0.0)) is True


def test_two_parallel_segments_never_cross():
    assert segments_cross((0.0, 0.0), (1.0, 0.0), (0.0, 1.0), (1.0, 1.0)) is False


def test_the_x_span_of_a_wedge_narrows_as_the_band_rises():
    """The diagonal reaches furthest left at the band's lowest edge."""
    low = poly_x_span(WEDGE, 0.95, 1.0)
    high = poly_x_span(WEDGE, 0.75, 0.80)
    assert low[0] < high[0]


def test_the_x_span_covers_a_band_the_polygon_only_crosses():
    """No vertex sits inside the band, so the span comes from the edge crossings."""
    assert poly_x_span(BAND, 0.04, 0.06) == (0.0, 1.0)


def test_a_band_the_polygon_never_reaches_has_no_x_span():
    assert poly_x_span(WEDGE, 0.1, 0.2) is None
