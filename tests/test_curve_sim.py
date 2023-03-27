from mtg_math import curve_sim

def test_curve_astuple_skips_draw_count():
    curve = curve_sim.Curve(11, 0, 14, 0, 12, 11, 8, 0, 42)
    assert curve.astuple() == (11, 0, 14, 0, 12, 11, 8, 42)
