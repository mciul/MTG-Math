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


def test_curve_decklist():
    curve = curve_sim.Curve(9, 0, 20, 14, 9, 4, 0, 0, 42)
    assert curve.decklist == {
        "1 CMC": 9,
        "2 CMC": 0,
        "3 CMC": 20,
        "4 CMC": 14,
        "5 CMC": 9,
        "Sol Ring": 1,
        "6 CMC": 4,
        "Rock": 0,
        "Draw": 0,
        "Land": 42,
    }


def test_curve_count():
    curve = curve_sim.Curve(11, 0, 14, 0, 12, 11, 8, 0, 42)
    assert curve.count == 98


def test_curve_distance_from_varying_one_count():
    curve1 = curve_sim.Curve(11, 0, 14, 0, 12, 11, 8, 0, 42)
    curve2 = curve_sim.Curve(11, 0, 16, 0, 12, 11, 8, 0, 42)
    assert curve1.distance_from(curve2) == 2


def test_curve_distance_from_varying_draw_is_zero():
    """draw is expected to always be zero, so this will give weird results"""
    curve1 = curve_sim.Curve(11, 0, 14, 0, 12, 11, 8, 1, 42)
    curve2 = curve_sim.Curve(11, 0, 14, 0, 12, 11, 8, 0, 42)
    assert curve1.distance_from(curve2) == 0


def test_curve_distance_from_varying_two_counts():
    curve1 = curve_sim.Curve(11, 0, 14, 0, 12, 11, 8, 0, 42)
    curve2 = curve_sim.Curve(11, 0, 15, 0, 11, 11, 8, 0, 42)
    assert curve1.distance_from(curve2) == 2


def test_curve_nearby_decks():
    curve = curve_sim.Curve.fromtuple((8, 19, 0, 16, 10, 3, 0, 42))
    decks = list(curve.nearby_decks())
    assert len(decks) == 3 * 3 * 2 * 3 * 3 * 3 * 2 * 3
    matches = [deck for deck in decks if deck == curve]
    assert len(matches) == 1
    for deck in decks:
        assert all(d >= 0 for d in deck.astuple())
        diff = [c - d for c, d in zip(curve.astuple(), deck.astuple())]
        assert all(d >= -1 for d in diff)
        assert all(d <= 1 for d in diff)


def test_curve_brief_desc():
    curve = curve_sim.Curve(8, 19, 0, 16, 10, 3, 0, 0, 42)
    assert curve.brief_desc() == "8, 19, 0, 16, 10, 3, 0, 42"


def test_curve_full_desc():
    curve = curve_sim.Curve(8, 19, 0, 16, 10, 3, 0, 0, 42)
    assert curve.full_desc() == (
        "8 one-drops, 19 two, 0 three, 16 four, 10 five, 3 six, 0 Signet, "
        "1 Sol Ring, 42 lands "
    )


def test_game_state_start_has_shuffled_library_and_hand():
    curve = curve_sim.Curve(6, 12, 13, 0, 13, 8, 7, 0, 39)
    state = curve_sim.GameState.start(curve)
    assert sum(state.hand.values()) == 7
    assert len(state.library) == 99 - 7
    for name, count in [
        ("1 CMC", 6),
        ("2 CMC", 12),
        ("3 CMC", 13),
        ("4 CMC", 0),
        ("5 CMC", 13),
        ("6 CMC", 8),
        ("Rock", 7),
        ("Sol Ring", 1),
        ("Land", 39),
    ]:
        matches = [card for card in state.library if card == name]
        assert len(matches) + state.hand[name] == count
