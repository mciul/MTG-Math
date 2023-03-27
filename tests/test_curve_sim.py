from mtg_math import curve_sim


def test_curve_astuple_skips_draw_count():
    curve = curve_sim.Curve(11, 0, 14, 0, 12, 11, 8, 0, 42)
    assert curve.astuple() == (11, 0, 14, 0, 12, 11, 8, 42)


def test_curve_fromtuple_doesnt_require_draw_count():
    curve = curve_sim.Curve.fromtuple((6, 12, 10, 14, 9, 0, 9, 38))
    assert curve == curve_sim.Curve(6, 12, 10, 14, 9, 0, 9, 0, 38)


def test_curve_copy():
    curve = curve_sim.Curve(11, 0, 14, 0, 12, 11, 8, 0, 42)
    assert curve.copy() is not curve
    assert curve.copy() == curve


def test_curve_count():
    curve = curve_sim.Curve(11, 0, 14, 0, 12, 11, 8, 0, 42)
    assert curve.count == 98
