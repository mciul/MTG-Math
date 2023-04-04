import random
from pytest import mark, raises
from mtg_math.curve_sim import (
    Curve,
    GameState,
    CardBag,
    do_we_keep,
    cards_to_bottom,
)

import logging

logger = logging.getLogger()
logging.basicConfig(level=logging.INFO)


def game_with_hand(hand: CardBag) -> GameState:
    curve = Curve(11, 0, 14, 0, 12, 11, 8, 0, 42)
    logger.info(f"game_with_hand({hand}) {curve.decklist=}")
    library = []
    for card, count in curve.decklist.items():
        library += [card] * (count - hand.get(card, 0))
    random.shuffle(library)
    return GameState(library, hand)


def test_curve_astuple_skips_draw_count():
    curve = Curve(11, 0, 14, 0, 12, 11, 8, 0, 42)
    assert curve.astuple() == (11, 0, 14, 0, 12, 11, 8, 42)


def test_curve_fromtuple_doesnt_require_draw_count():
    curve = Curve.fromtuple((6, 12, 10, 14, 9, 0, 9, 38))
    assert curve == Curve(6, 12, 10, 14, 9, 0, 9, 0, 38)


def test_curve_copy():
    curve = Curve(11, 0, 14, 0, 12, 11, 8, 0, 42)
    assert curve.copy() is not curve
    assert curve.copy() == curve


def test_curve_decklist():
    curve = Curve(9, 0, 20, 14, 9, 4, 0, 0, 42)
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
    curve = Curve(11, 0, 14, 0, 12, 11, 8, 0, 42)
    assert curve.count == 98


def test_curve_distance_from_varying_one_count():
    curve1 = Curve(11, 0, 14, 0, 12, 11, 8, 0, 42)
    curve2 = Curve(11, 0, 16, 0, 12, 11, 8, 0, 42)
    assert curve1.distance_from(curve2) == 2


def test_curve_distance_from_varying_draw_is_zero():
    """draw is expected to always be zero, so this will give weird results"""
    curve1 = Curve(11, 0, 14, 0, 12, 11, 8, 1, 42)
    curve2 = Curve(11, 0, 14, 0, 12, 11, 8, 0, 42)
    assert curve1.distance_from(curve2) == 0


def test_curve_distance_from_varying_two_counts():
    curve1 = Curve(11, 0, 14, 0, 12, 11, 8, 0, 42)
    curve2 = Curve(11, 0, 15, 0, 11, 11, 8, 0, 42)
    assert curve1.distance_from(curve2) == 2


def test_curve_nearby_decks():
    curve = Curve.fromtuple((8, 19, 0, 16, 10, 3, 0, 42))
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
    curve = Curve(8, 19, 0, 16, 10, 3, 0, 0, 42)
    assert curve.brief_desc() == "8, 19, 0, 16, 10, 3, 0, 42"


def test_curve_full_desc():
    curve = Curve(8, 19, 0, 16, 10, 3, 0, 0, 42)
    assert curve.full_desc() == (
        "8 one-drops, 19 two, 0 three, 16 four, 10 five, 3 six, 0 Signet, "
        "1 Sol Ring, 42 lands "
    )


def test_game_state_start_has_shuffled_library_and_hand():
    curve = Curve(6, 12, 13, 0, 13, 8, 7, 0, 39)
    state = GameState.start(curve.decklist)
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


def test_game_state_add_to_hand():
    curve = Curve(6, 12, 13, 0, 13, 8, 7, 0, 39)
    state = GameState.start(curve.decklist)
    orig_hand = state.hand.copy()
    orig_2cmc = orig_hand["2 CMC"]
    state.add_to_hand(CardBag({"2 CMC": 1}))
    assert state.hand["2 CMC"] == orig_2cmc + 1
    assert state.hand == orig_hand + CardBag({"2 CMC": 1})


def test_bottom_three_lands():
    state = game_with_hand(CardBag({"Land": 7}))
    state.bottom_from_hand(CardBag({"Land": 3}))
    assert state.hand == CardBag({"Land": 4})


def test_bottom_lands_and_spells():
    state = game_with_hand(CardBag({"1 CMC": 1, "6 CMC": 2, "Land": 4}))
    state.bottom_from_hand(CardBag({"Land": 1, "6 CMC": 1}))
    assert state.hand == CardBag({"1 CMC": 1, "6 CMC": 1, "Land": 3})


def test_game_state_draw_updates_state_and_returns_drawn_card():
    state = game_with_hand(CardBag({"Land": 4, "1 CMC": 1}))
    old_library = state.library.copy()
    drawn = state.draw()
    assert state.hand == CardBag({"Land": 4, "1 CMC": 1}).add(drawn, 1)
    assert state.library == old_library[1:]


def test_game_state_play_from_hand_removes_card_from_hand():
    state = game_with_hand(CardBag({"Land": 4, "1 CMC": 2}))
    state.play_from_hand(CardBag({"Land": 1}))
    assert state.hand == CardBag({"Land": 3, "1 CMC": 2})


@mark.parametrize(
    "count,free", [(7, True), (7, False), (6, False), (5, False)]
)
def test_do_we_keep_perfect_curveout(count, free):
    hand = CardBag({"1 CMC": 1, "2 CMC": 1, "3 CMC": 1, "4 CMC": 1, "Land": 3})
    assert do_we_keep(hand, cards_to_keep=count, free=free)


@mark.parametrize(
    "count,free", [(7, True), (7, False), (6, False), (5, False)]
)
def test_do_we_keep_perfect_ramp(count, free):
    hand = CardBag({"1 CMC": 1, "Rock": 1, "4 CMC": 1, "Land": 4})
    assert do_we_keep(hand, cards_to_keep=count, free=free)


@mark.parametrize("free", [True, False])
def test_do_we_keep_seven_with_five_lands_and_two_spells(free):
    hand = CardBag({"Land": 5, "6 CMC": 2})
    assert do_we_keep(hand, 7, free=free)


@mark.parametrize("keep", [6, 5])
@mark.parametrize("spells", [2, 3, 4, 5])
def test_do_we_keep_less_with_good_balance(keep: int, spells: int):
    hand = CardBag({"Land": 7 - spells, "6 CMC": spells})
    assert do_we_keep(hand, keep)


@mark.parametrize("max_rocks", [1, 2])
@mark.parametrize("spells", [2, 3])
@mark.parametrize("free", [True, False])
def test_do_we_keep_seven_with_moderate_rocks(max_rocks, spells, free):
    rocks = min(max_rocks, 4 - spells)
    lands = 7 - spells - rocks
    hand = CardBag(
        {"Land": 7 - spells - rocks, "Rock": rocks, "1 CMC": spells}
    )
    assert do_we_keep(hand, 7, free=free)


def test_do_we_keep_seven_with_two_lands_and_three_rocks_or_go_to_six():
    hand = CardBag({"Land": 2, "Rock": 3, "1 CMC": 2})
    assert do_we_keep(hand, 7, free=False)


@mark.parametrize("rocks", [1, 2, 3, 4, 5])
@mark.parametrize("spells", [0, 1])
@mark.parametrize("free", [True, False])
def test_do_we_keep_seven_with_lots_of_rocks(spells, rocks, free):
    hand = CardBag(
        {"Land": 7 - spells - rocks, "Rock": rocks, "1 CMC": spells}
    )
    assert not do_we_keep(hand, 7, free=free)


@mark.parametrize("spells", [0, 1])
@mark.parametrize("keep", [6, 5, 4])
def test_do_we_keep_less_with_five_lands_and_rocks(spells, keep):
    hand = CardBag({"Land": 5, "Rock": 2 - spells, "6 CMC": spells})
    assert do_we_keep(hand, cards_to_keep=keep)


@mark.parametrize("spells", [0, 1])
@mark.parametrize("free", [True, False])
def test_do_we_keep_seven_with_six_or_more_lands(spells, free):
    hand = CardBag({"Land": 7 - spells, "2 CMC": spells})
    assert not do_we_keep(hand, 7, free=free)


def test_do_we_keep_six_with_six_lands():
    hand = CardBag({"Land": 6, "1 CMC": 1})
    assert not do_we_keep(hand, 6)


def test_do_we_keep_five_with_six_lands():
    hand = CardBag({"Land": 6, "1 CMC": 1})
    assert do_we_keep(hand, 5)


@mark.parametrize("keep", [6, 5])
def test_do_we_keep_more_than_four_with_seven_lands(keep):
    hand = CardBag({"Land": 7})
    assert not do_we_keep(hand, keep)


@mark.parametrize(
    "count,free", [(7, True), (7, False), (6, False), (5, False)]
)
def test_do_we_keep_one_land_with_sol_ring(free, count):
    hand = CardBag({"Land": 1, "Sol Ring": 1, "6 CMC": 4})
    assert do_we_keep(hand, cards_to_keep=count, free=free)


@mark.parametrize(
    "count,free", [(7, True), (7, False), (6, False), (5, False)]
)
def test_do_we_keep_one_land_no_sol_ring(free, count):
    hand = CardBag({"Land": 1, "1 CMC": 6})
    assert not do_we_keep(hand, cards_to_keep=count, free=free)


def test_do_we_keep_two_lands_no_sol_ring_free_mulligan():
    hand = CardBag({"Land": 2, "Rock": 3, "1 CMC": 1, "3 CMC": 1})
    assert not do_we_keep(hand, 7, free=True)


@mark.parametrize("count", [7, 6, 5])
def test_do_we_keep_two_lands_no_free_mulligan(count):
    hand = CardBag({"Land": 2, "6 CMC": 5})
    assert do_we_keep(hand, cards_to_keep=count, free=False)


@mark.parametrize("spells", [1, 2, 3, 4, 5, 6, 7])
def test_do_we_keep_four(spells: int):
    hand = CardBag({"Land": 7 - spells, "6 CMC": spells})
    assert do_we_keep(hand, 4)


def test_cardbag_equal_with_zeros():
    assert CardBag({"Land": 7}) == CardBag({"Land": 7, "Sol Ring": 0})


def test_cardbag_with_negative_count_raises_error():
    with raises(ValueError):
        CardBag({"2 CMC": 2, "Sol Ring": 0, "Land": -1})


def test_cardbag_minus():
    bag1 = CardBag({"Land": 2, "1 CMC": 2, "4 CMC": 1})
    bag2 = CardBag({"1 CMC": 1, "4 CMC": 1})
    assert bag1 - bag2 == CardBag({"Land": 2, "1 CMC": 1})


def test_cardbag_minus_too_much_stops_at_zero():
    bag1 = CardBag({"Land": 2, "Sol Ring": 1})
    bag2 = CardBag({"Land": 3})
    assert bag1 - bag2 == CardBag({"Sol Ring": 1})


def test_cardbag_minus_card_we_dont_have_does_nothing():
    bag1 = CardBag({"Land": 2})
    bag2 = CardBag({"Land": 1, "Sol Ring": 1})
    assert bag1 - bag2 == CardBag({"Land": 1})


def test_cardbag_plus():
    bag1 = CardBag({"Land": 2, "1 CMC": 1, "2 CMC": 1})
    bag2 = CardBag({"2 CMC": 1, "4 CMC": 1})
    assert bag1 + bag2 == CardBag(
        {"Land": 2, "1 CMC": 1, "2 CMC": 2, "4 CMC": 1}
    )


def test_cards_to_bottom_when_keeping_seven():
    hand = CardBag({"Land": 4, "Rock": 1, "1 CMC": 2})
    assert cards_to_bottom(hand, 0) == {}


@mark.parametrize("lands", [4, 5])
def test_cards_to_bottom_when_keeping_six_with_too_much_land(lands):
    hand = CardBag({"Land": lands, "1 CMC": 1, "6 CMC": 6 - lands})
    assert cards_to_bottom(hand, 1) == {"Land": 1}


@mark.parametrize("sol_ring", [0, 1])
@mark.parametrize("rocks", [3, 4, 5])
def test_cards_to_bottom_when_keeping_six_with_too_many_rocks(sol_ring, rocks):
    hand = CardBag(
        {
            "Land": 2 - sol_ring,
            "Sol Ring": sol_ring,
            "Rock": rocks,
            "5 CMC": 5 - rocks,
        }
    )
    assert cards_to_bottom(hand, 1) == {"Rock": 1}


@mark.parametrize("rocks", [2, 3, 4])
def test_cards_to_bottom_when_keeping_six_with_too_many_rocks_and_land(rocks):
    hand = CardBag({"Land": 3, "Rock": rocks, "5 CMC": 4 - rocks})
    assert cards_to_bottom(hand, 1) == {"Rock": 1}


@mark.parametrize("count", [1, 2, 3])
def test_cards_to_bottom_when_keeping_six_with_six_cmc(count):
    hand = CardBag(
        {"Land": 2, "Rock": 3 - count, "4 CMC": 1, "5 CMC": 1, "6 CMC": count}
    )
    assert cards_to_bottom(hand, 1) == {"6 CMC": 1}


@mark.parametrize("count", [1, 2, 3])
def test_cards_to_bottom_when_keeping_six_with_five_cmc(count):
    hand = CardBag(
        {"Land": 2, "Rock": 3 - count, "3 CMC": 1, "4 CMC": 1, "5 CMC": count}
    )
    assert cards_to_bottom(hand, 1) == {"5 CMC": 1}


@mark.parametrize("count", [1, 2, 3])
def test_cards_to_bottom_when_keeping_six_with_four_cmc(count):
    hand = CardBag(
        {"Land": 2, "Rock": 3 - count, "2 CMC": 1, "3 CMC": 1, "4 CMC": count}
    )
    assert cards_to_bottom(hand, 1) == {"4 CMC": 1}


@mark.parametrize("count", [1, 2, 3])
def test_cards_to_bottom_when_keeping_six_with_three_cmc(count):
    hand = CardBag(
        {"Land": 2, "Rock": 3 - count, "1 CMC": 1, "2 CMC": 1, "3 CMC": count}
    )
    assert cards_to_bottom(hand, 1) == {"3 CMC": 1}


@mark.parametrize("count", [1, 2, 3, 4])
def test_cards_to_bottom_when_keeping_six_with_two_cmc(count):
    hand = CardBag({"Land": 2, "Rock": 1, "1 CMC": 4 - count, "2 CMC": count})
    assert cards_to_bottom(hand, 1) == {"2 CMC": 1}


@mark.parametrize("count", [3, 4, 5])
def test_cards_to_bottom_when_keeping_six_with_one_cmc(count):
    hand = CardBag({"Land": 6 - count, "Rock": 1, "1 CMC": count})
    assert cards_to_bottom(hand, 1) == {"1 CMC": 1}


@mark.parametrize(
    "cards,bottom",
    [
        ({"Land": 6, "Rock": 1}, {"Land": 2}),
        ({"Land": 6, "6 CMC": 1}, {"Land": 2}),
        ({"Land": 6, "Rock": 1}, {"Land": 2}),
        ({"Land": 5, "Rock": 1, "6 CMC": 1}, {"Land": 2}),
        ({"Land": 4, "Rock": 2, "6 CMC": 1}, {"Land": 1, "Rock": 1}),
        ({"Land": 3, "Rock": 3, "6 CMC": 1}, {"Rock": 2}),
        (
            {"Land": 3, "Rock": 2, "5 CMC": 1, "6 CMC": 1},
            {"Rock": 1, "6 CMC": 1},
        ),
        ({"Land": 2, "Rock": 3, "5 CMC": 1, "6 CMC": 1}, {"Rock": 2}),
        ({"Land": 2, "Rock": 2, "5 CMC": 1, "6 CMC": 2}, {"6 CMC": 2}),
        (
            {"Land": 2, "Rock": 2, "5 CMC": 2, "6 CMC": 1},
            {"5 CMC": 1, "6 CMC": 1},
        ),
        (
            {"Land": 1, "Sol Ring": 1, "Rock": 2, "5 CMC": 2, "6 CMC": 1},
            {"5 CMC": 1, "6 CMC": 1},
        ),
    ],
)
def test_cards_to_bottom_when_keeping_five(cards, bottom):
    hand = CardBag(cards)
    assert cards_to_bottom(hand, 2) == CardBag(bottom)


@mark.parametrize(
    "cards,bottom",
    [
        ({"Land": 7}, {"Land": 3}),
        ({"Land": 6, "6 CMC": 1}, {"Land": 3}),
        ({"Land": 6, "Rock": 1}, {"Land": 3}),
        ({"Land": 6, "Sol Ring": 1}, {"Land": 3}),
        ({"Land": 5, "Rock": 1, "6 CMC": 1}, {"Land": 2, "6 CMC": 1}),
        ({"Land": 5, "Rock": 2}, {"Land": 2, "Rock": 1}),
        ({"Land": 5, "Sol Ring": 1, "Rock": 1}, {"Land": 3}),
        ({"Land": 5, "Sol Ring": 1, "6 CMC": 1}, {"Land": 3}),
        (
            {"Land": 4, "Rock": 2, "6 CMC": 1},
            {"Land": 1, "Rock": 1, "6 CMC": 1},
        ),
        ({"Land": 4, "Rock": 3}, {"Land": 1, "Rock": 2}),
        ({"Land": 4, "Sol Ring": 1, "Rock": 2}, {"Land": 2, "Rock": 1}),
        ({"Land": 3, "Rock": 3, "6 CMC": 1}, {"Rock": 2, "6 CMC": 1}),
        (
            {"Land": 3, "Rock": 2, "5 CMC": 1, "6 CMC": 1},
            {"Rock": 1, "5 CMC": 1, "6 CMC": 1},
        ),
        ({"Land": 3, "Rock": 4}, {"Rock": 3}),
        ({"Land": 3, "Sol Ring": 1, "Rock": 4}, {"Rock": 3}),
        (
            {"Land": 2, "Rock": 3, "5 CMC": 1, "6 CMC": 1},
            {"Rock": 2, "6 CMC": 1},
        ),
        (
            {"Land": 2, "Rock": 2, "5 CMC": 1, "6 CMC": 2},
            {"5 CMC": 1, "6 CMC": 2},
        ),
        (
            {"Land": 2, "Rock": 2, "5 CMC": 2, "6 CMC": 1},
            {"5 CMC": 2, "6 CMC": 1},
        ),
        ({"Land": 2, "Rock": 5}, {"Rock": 3}),
        ({"Land": 2, "Sol Ring": 1, "Rock": 4}, {"Rock": 3}),
        (
            {"Land": 1, "Sol Ring": 1, "Rock": 2, "5 CMC": 2, "6 CMC": 1},
            {"5 CMC": 2, "6 CMC": 1},
        ),
        ({"Land": 1, "Rock": 6}, {"Rock": 3}),
        ({"Land": 1, "Sol Ring": 1, "Rock": 5}, {"Rock": 3}),
        (
            {
                "1 CMC": 2,
                "2 CMC": 1,
                "3 CMC": 1,
                "4 CMC": 1,
                "5 CMC": 1,
                "6 CMC": 1,
            },
            {"4 CMC": 1, "5 CMC": 1, "6 CMC": 1},
        ),
        ({"Rock": 2, "6 CMC": 5}, {"6 CMC": 3}),
        ({"Rock": 3, "6 CMC": 4}, {"Rock": 2, "6 CMC": 1}),
        ({"Rock": 4, "6 CMC": 4}, {"Rock": 3}),
        ({"Rock": 6, "Sol Ring": 1}, {"Rock": 3}),
        ({"Rock": 7}, {"Rock": 3}),
    ],
)
def test_cards_to_bottom_when_keeping_four(cards, bottom):
    hand = CardBag(cards)
    assert cards_to_bottom(hand, 3) == CardBag(bottom)
