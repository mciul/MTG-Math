import logging
import random
from copy import deepcopy

from pytest import mark, raises, approx

from mtg_math.curve_sim import (
    CardBag,
    Curve,
    GameState,
    cards_to_bottom,
    do_we_keep,
    take_turn,
)

logger = logging.getLogger()
logging.basicConfig(level=logging.DEBUG)


def game_with_hand(hand: CardBag) -> GameState:
    curve = Curve(11, 0, 14, 0, 12, 11, 8, 0, 42)
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


def test_game_state_untap_updates_mana_available():
    state = GameState(
        ["Land"],
        CardBag({}),
        mana_available=2,
        lands_in_play=6,
        rocks_in_play=3,
    )
    new_state = state.untap()
    assert new_state == GameState(
        ["Land"],
        CardBag({}),
        mana_available=9,
        lands_in_play=6,
        rocks_in_play=3,
    )


def test_game_state_untap_compounds_mana_spent():
    state = GameState(
        ["Land"],
        CardBag({}),
        cumulative_mana_in_play=3.0,
        compounded_mana_spent=3.0,
    )
    new_state = state.untap()
    assert new_state == GameState(
        ["Land"],
        CardBag({}),
        cumulative_mana_in_play=3.0,
        compounded_mana_spent=6.0,
    )


def test_game_state_play_from_hand_updates_lands_and_rocks():
    hand = CardBag({"Land": 1, "Rock": 1, "Sol Ring": 1})
    initial_state = GameState(
        ["Land"],
        CardBag({"Land": 1, "6 CMC": 1, "Rock": 1, "Sol Ring": 1}),
        cumulative_mana_in_play=1.0,
        compounded_mana_spent=2.0,
    )
    new_state = initial_state.play_from_hand(hand)
    assert new_state == GameState(
        ["Land"],
        CardBag({"6 CMC": 1}),
        lands_in_play=1,
        rocks_in_play=3,
        mana_available=1,
        cumulative_mana_in_play=1.0,
        compounded_mana_spent=2.0,
    )


def test_game_state_play_from_hand_land_increases_mana_available():
    initial_state = GameState(["Land"], CardBag({"Land": 2}), mana_available=0)
    new_state = initial_state.play_from_hand(CardBag({"Land": 1}))
    assert new_state == GameState(
        ["Land"], CardBag({"Land": 1}), lands_in_play=1, mana_available=1
    )


def test_game_state_play_from_hand_rock_decreases_mana_available():
    initial_state = GameState(["Land"], CardBag({"Rock": 2}), mana_available=2)
    new_state = initial_state.play_from_hand(CardBag({"Rock": 1}))
    assert new_state == GameState(
        ["Land"],
        CardBag({"Rock": 1}),
        rocks_in_play=1,
        mana_available=1,
    )


def test_game_state_play_from_hand_sol_ring_increases_mana_available():
    initial_state = GameState(
        ["Land"], CardBag({"Sol Ring": 1}), mana_available=1
    )
    new_state = initial_state.play_from_hand(CardBag({"Sol Ring": 1}))
    assert new_state == GameState(
        ["Land"],
        CardBag({}),
        rocks_in_play=2,
        mana_available=2,
    )


@mark.parametrize(
    "spell,count,mana,value,compound_value",
    [
        ("1 CMC", 1, 1, 2.0, 3.0),
        ("1 CMC", 3, 3, 4.0, 5.0),
        ("2 CMC", 1, 2, 3.0, 4.0),
        ("2 CMC", 2, 4, 5.0, 6.0),
        ("3 CMC", 1, 3, 4.0, 5.0),
        ("4 CMC", 1, 4, 5.0, 6.0),
        ("5 CMC", 1, 5, 6.0, 7.0),
        ("6 CMC", 1, 6, 7.2, 8.2),
        ("6 CMC", 2, 12, 13.4, 14.4),
    ],
)
def test_game_state_play_from_hand_updates_spells(
    spell, count, mana, value, compound_value
):
    hand = CardBag({spell: count})
    initial_state = GameState(
        ["Land"],
        deepcopy(hand),
        mana_available=mana,
        cumulative_mana_in_play=1.0,
        compounded_mana_spent=2.0,
    )
    new_state = initial_state.play_from_hand(hand)
    assert new_state == GameState(
        ["Land"],
        CardBag({}),
        mana_available=0,
        cumulative_mana_in_play=value,
        compounded_mana_spent=compound_value,
    )


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


@mark.parametrize(
    "starting_state,ending_state",
    [
        (
            # play the land we drew
            GameState(
                ["Land", "Rock"],
                CardBag({"4 CMC": 2, "6 CMC": 1, "Land": 3}),
            ),
            GameState(
                ["Rock"],
                CardBag({"4 CMC": 2, "6 CMC": 1, "Land": 3}),
                lands_in_play=1,
                mana_available=1,
            ),
        ),
        (
            # draw an expensive spell - all we can do is play a land
            GameState(
                ["5 CMC", "Land"],
                CardBag({"4 CMC": 1, "5 CMC": 5, "Land": 2}),
            ),
            GameState(
                ["Land"],
                CardBag({"4 CMC": 1, "5 CMC": 6, "Land": 1}),
                lands_in_play=1,
                mana_available=1,
            ),
        ),
        (
            # play a land, a Sol Ring, and a rock
            GameState(
                ["Rock", "Land"],
                CardBag({"6 CMC": 2, "Rock": 2, "Sol Ring": 1, "Land": 3}),
            ),
            GameState(
                ["Land"],
                CardBag({"6 CMC": 2, "Rock": 2, "Land": 2}),
                lands_in_play=1,
                rocks_in_play=3,
            ),
        ),
        (
            # play a land and a 1-drop
            GameState(
                ["2 CMC", "3 CMC"],
                CardBag({"1 CMC": 1, "2 CMC": 3, "Land": 3}),
            ),
            GameState(
                ["3 CMC"],
                CardBag({"1 CMC": 0, "2 CMC": 4, "Land": 2}),
                lands_in_play=1,
                cumulative_mana_in_play=1.0,
                compounded_mana_spent=1.0,
            ),
        ),
        (
            # 1 CMC x 2 and 2 CMC with Sol Ring
            # For some reason, the simulator doesn't let us cast our
            # 1-drop or 2-drop with the Sol Ring - color restrictions?
            GameState(
                ["2 CMC", "3 CMC"],
                CardBag({"1 CMC": 2, "Sol Ring": 1, "2 CMC": 3, "Land": 1}),
            ),
            GameState(
                ["3 CMC"],
                CardBag({"1 CMC": 2, "2 CMC": 4, "Land": 0}),
                lands_in_play=1,
                rocks_in_play=2,
                cumulative_mana_in_play=0.0,
                compounded_mana_spent=0.0,
            ),
        ),
        (
            # 1 CMC with rock and Sol Ring
            # Even with our "Arcane Signet," the simulator doesn't assume
            # we can cast a 1-drop. True for Ravnica signets I guess.
            GameState(
                ["Rock", "3 CMC"],
                CardBag({"1 CMC": 2, "Sol Ring": 1, "Rock": 3, "Land": 2}),
            ),
            GameState(
                ["3 CMC"],
                CardBag({"1 CMC": 2, "Rock": 3, "Land": 1}),
                lands_in_play=1,
                rocks_in_play=3,
                cumulative_mana_in_play=0.0,
                compounded_mana_spent=0.0,
            ),
        ),
        (
            # mull to 4, 1-drop commander, no land
            GameState(["Rock", "Land"], CardBag({"1 CMC": 3, "Rock": 2})),
            GameState(
                ["Land"], CardBag({"1 CMC": 3, "Rock": 3}), lands_in_play=0
            ),
        ),
    ],
)
def test_take_turn_one(starting_state, ending_state):
    assert take_turn(starting_state, 1) == ending_state


@mark.parametrize(
    "starting_state,ending_state",
    [
        (
            # land and 1-drop in play, second 1-drop available
            GameState(
                ["1 CMC", "Rock"],
                CardBag({"6 CMC": 3, "Land": 4}),
                lands_in_play=1,
                cumulative_mana_in_play=1.0,
                compounded_mana_spent=1.0,
            ),
            GameState(
                ["Rock"],
                CardBag({"6 CMC": 3, "Land": 3}),
                lands_in_play=2,
                mana_available=1,
                cumulative_mana_in_play=2.0,
                compounded_mana_spent=3.0,
            ),
        ),
        (
            # land 1-drop in play, two more 1-drops available
            GameState(
                ["1 CMC", "Rock"],
                CardBag({"1 CMC": 1, "3 CMC": 3, "Land": 3}),
                lands_in_play=1,
                cumulative_mana_in_play=1.0,
                compounded_mana_spent=1.0,
            ),
            GameState(
                ["Rock"],
                CardBag({"3 CMC": 3, "Land": 2}),
                lands_in_play=2,
                mana_available=0,
                cumulative_mana_in_play=3.0,
                compounded_mana_spent=4.0,
            ),
        ),
        (
            # land in play, 2 drop available
            GameState(
                ["1 CMC", "Rock"],
                CardBag({"2 CMC": 1, "3 CMC": 3, "Land": 3}),
                lands_in_play=1,
                cumulative_mana_in_play=0.0,
                compounded_mana_spent=0.0,
            ),
            GameState(
                ["Rock"],
                CardBag({"1 CMC": 1, "3 CMC": 3, "Land": 2}),
                lands_in_play=2,
                mana_available=0,
                cumulative_mana_in_play=2.0,
                compounded_mana_spent=2.0,
            ),
        ),
        (
            # land and 1-drop in play, rock and 2-drop available
            GameState(
                ["Rock", "1 CMC"],
                CardBag({"2 CMC": 3, "Land": 3}),
                lands_in_play=1,
                cumulative_mana_in_play=1.0,
                compounded_mana_spent=1.0,
            ),
            GameState(
                ["1 CMC"],
                CardBag({"2 CMC": 3, "Land": 2}),
                lands_in_play=2,
                rocks_in_play=1,
                mana_available=1,
                cumulative_mana_in_play=1.0,
                compounded_mana_spent=2.0,
            ),
        ),
        (
            # land and 1-drop in play, rock and 1 and 2 drops available
            GameState(
                ["1 CMC", "1 CMC"],
                CardBag({"Rock": 1, "2 CMC": 3, "Land": 2}),
                lands_in_play=1,
                cumulative_mana_in_play=1.0,
                compounded_mana_spent=1.0,
            ),
            GameState(
                ["1 CMC"],
                CardBag({"2 CMC": 3, "Land": 1}),
                lands_in_play=2,
                rocks_in_play=1,
                mana_available=0,
                cumulative_mana_in_play=2.0,
                compounded_mana_spent=3.0,
            ),
        ),
        (
            # land and 1-drop in play, land in hand, sol ring drawn...
            # rock and 2 drops in hand
            GameState(
                ["Sol Ring", "1 CMC"],
                CardBag({"Rock": 1, "2 CMC": 3, "Land": 2}),
                lands_in_play=1,
                cumulative_mana_in_play=1.0,
                compounded_mana_spent=1.0,
            ),
            GameState(
                ["1 CMC"],
                CardBag({"2 CMC": 2, "Land": 1}),
                lands_in_play=2,
                rocks_in_play=3,
                mana_available=0,
                cumulative_mana_in_play=3.0,
                compounded_mana_spent=4.0,
            ),
        ),
        (
            # land & 1-drop in play, no land in hand, sol ring drawn
            # (mull to 4)
            GameState(
                ["Sol Ring", "1 CMC"],
                CardBag({"5 CMC": 4}),
                lands_in_play=1,
                cumulative_mana_in_play=1.0,
                compounded_mana_spent=1.0,
            ),
            GameState(
                ["1 CMC"],
                CardBag({"5 CMC": 4}),
                lands_in_play=1,
                rocks_in_play=2,
                mana_available=2,
                cumulative_mana_in_play=1.0,
                compounded_mana_spent=2.0,
            ),
        ),
        (
            # land and sol ring in play no second land and no spells
            GameState(
                ["4 CMC", "1 CMC"],
                CardBag({"4 CMC": 4}),
                lands_in_play=1,
                rocks_in_play=2,
                cumulative_mana_in_play=0.0,
                compounded_mana_spent=0.0,
            ),
            GameState(
                ["1 CMC"],
                CardBag({"4 CMC": 5}),
                lands_in_play=1,
                rocks_in_play=2,
                mana_available=3,
                cumulative_mana_in_play=0.0,
                compounded_mana_spent=0.0,
            ),
        ),
        (
            # Land and Sol Ring in play, 3 drop but no second land
            GameState(
                ["4 CMC", "1 CMC"],
                CardBag({"1 CMC": 1, "2 CMC": 1, "3 CMC": 2}),
                lands_in_play=1,
                rocks_in_play=2,
                cumulative_mana_in_play=0.0,
                compounded_mana_spent=0.0,
            ),
            GameState(
                ["1 CMC"],
                CardBag({"1 CMC": 1, "2 CMC": 1, "3 CMC": 1, "4 CMC": 1}),
                lands_in_play=1,
                rocks_in_play=2,
                mana_available=0,
                cumulative_mana_in_play=3.0,
                compounded_mana_spent=3.0,
            ),
        ),
        (
            # Land and Sol Ring in play, 1 and 2 drops but no second land
            GameState(
                ["4 CMC", "1 CMC"],
                CardBag({"1 CMC": 2, "2 CMC": 2}),
                lands_in_play=1,
                rocks_in_play=2,
                cumulative_mana_in_play=0.0,
                compounded_mana_spent=0.0,
            ),
            GameState(
                ["1 CMC"],
                CardBag({"1 CMC": 1, "2 CMC": 1, "4 CMC": 1}),
                lands_in_play=1,
                rocks_in_play=2,
                mana_available=0,
                cumulative_mana_in_play=3.0,
                compounded_mana_spent=3.0,
            ),
        ),
        (
            # Land and Sol Ring in play, 4 drop and second land
            GameState(
                ["4 CMC", "1 CMC"],
                CardBag({"1 CMC": 2, "2 CMC": 2, "Land": 1}),
                lands_in_play=1,
                rocks_in_play=2,
                cumulative_mana_in_play=0.0,
                compounded_mana_spent=0.0,
            ),
            GameState(
                ["1 CMC"],
                CardBag({"1 CMC": 2, "2 CMC": 2}),
                lands_in_play=2,
                rocks_in_play=2,
                mana_available=0,
                cumulative_mana_in_play=4.0,
                compounded_mana_spent=4.0,
            ),
        ),
        (
            # Land and Sol Ring in play, second land and 1, 2, 3 drops
            GameState(
                ["3 CMC", "1 CMC"],
                CardBag({"1 CMC": 2, "2 CMC": 2, "3 CMC": 1, "Land": 1}),
                lands_in_play=1,
                rocks_in_play=2,
                cumulative_mana_in_play=0.0,
                compounded_mana_spent=0.0,
            ),
            GameState(
                ["1 CMC"],
                CardBag({"1 CMC": 2, "3 CMC": 2}),
                lands_in_play=2,
                rocks_in_play=2,
                mana_available=0,
                cumulative_mana_in_play=4.0,
                compounded_mana_spent=4.0,
            ),
        ),
        (
            # Land and Sol Ring in play, second land, one 2 drop and 3 drops
            GameState(
                ["3 CMC", "1 CMC"],
                CardBag({"2 CMC": 1, "3 CMC": 1, "Land": 2}),
                lands_in_play=1,
                rocks_in_play=2,
                cumulative_mana_in_play=0.0,
                compounded_mana_spent=0.0,
            ),
            GameState(
                ["1 CMC"],
                CardBag({"2 CMC": 1, "3 CMC": 1, "Land": 1}),
                lands_in_play=2,
                rocks_in_play=2,
                mana_available=1,
                cumulative_mana_in_play=3.0,
                compounded_mana_spent=3.0,
            ),
        ),
        (
            # no land in play, Sol Ring in hand, draw land (mull to 4)
            # this illustrates the weird behavior of Turn 1 -
            # in the case of Turn 2, the 2-drop will be cast, even though
            # it wouldn't in the identical Turn 1 case
            GameState(
                ["Land", "1 CMC"],
                CardBag({"1 CMC": 2, "2 CMC": 2, "Sol Ring": 1}),
                lands_in_play=0,
                rocks_in_play=0,
            ),
            GameState(
                ["1 CMC"],
                CardBag({"1 CMC": 2, "2 CMC": 1}),
                lands_in_play=1,
                rocks_in_play=2,
                mana_available=0,
                cumulative_mana_in_play=2.0,
                compounded_mana_spent=2.0,
            ),
        )
        # if one were feeling diligent, one could add these cases...
        # no land and 1 drop
        # no land and Sol ring....
        # with 1 land and 1 rock in play...
        #
        # with 1 land and 3 rocks (Sol Ring + Signet) in play...
    ],
)
def test_take_turn_two(starting_state, ending_state):
    assert take_turn(starting_state, 2) == ending_state


@mark.parametrize(
    "starting_state,ending_state",
    [
        (
            # land and 1-drop in play, rock and 2-drop available
            # we'll cast the 2-drop on turn 3 - on turn 2 it would be the rock
            GameState(
                ["Rock", "1 CMC"],
                CardBag({"2 CMC": 3, "Land": 3}),
                lands_in_play=1,
                cumulative_mana_in_play=1.0,
                compounded_mana_spent=1.0,
            ),
            GameState(
                ["1 CMC"],
                CardBag({"2 CMC": 2, "Rock": 1, "Land": 2}),
                lands_in_play=2,
                rocks_in_play=0,
                mana_available=0,
                cumulative_mana_in_play=3.0,
                compounded_mana_spent=4.0,
            ),
        ),
        (
            # 1-drop, 2 lands and a rock in play - cast a rock and a 3-drop
            # instead of a 4-drop
            GameState(
                ["Rock", "1 CMC"],
                CardBag({"3 CMC": 1, "4 CMC": 1, "Land": 1}),
                lands_in_play=2,
                rocks_in_play=1,
                cumulative_mana_in_play=1.0,
                compounded_mana_spent=2.0,
            ),
            GameState(
                ["1 CMC"],
                CardBag({"4 CMC": 1}),
                lands_in_play=3,
                rocks_in_play=2,
                mana_available=0,
                cumulative_mana_in_play=4.0,
                compounded_mana_spent=6.0,
            ),
        ),
        (
            # Sol Ring and 3 rocks in play with 4-drop and 3-drop
            # cast a rock before the spells
            GameState(
                ["Rock", "1 CMC"],
                CardBag({"3 CMC": 1, "4 CMC": 1, "Land": 1}),
                lands_in_play=2,
                rocks_in_play=5,
            ),
            GameState(
                ["1 CMC"],
                CardBag({}),
                lands_in_play=3,
                rocks_in_play=6,
                mana_available=0,
                cumulative_mana_in_play=7.0,
                compounded_mana_spent=7.0,
            ),
        ),
        (
            # Sol Ring and 3 rocks in play with 1-drop, 4-drop and rock
            # cast all if there's nothing else to do with the mana
            # this is a real example from og runtime logs
            # (although it was actually turn 5)
            GameState(
                ["Rock", "1 CMC"],
                CardBag({"1 CMC": 1, "4 CMC": 1}),
                lands_in_play=2,
                rocks_in_play=5,
                cumulative_mana_in_play=15.2,
                compounded_mana_spent=25.4,
            ),
            GameState(
                ["1 CMC"],
                CardBag({}),
                lands_in_play=2,
                rocks_in_play=6,
                mana_available=1,
                cumulative_mana_in_play=20.2,
                compounded_mana_spent=approx(45.6),
            ),
        ),
    ],
)
@mark.parametrize("turn", [3, 4])
def test_take_turn_three_or_four(starting_state, ending_state, turn):
    state = deepcopy(starting_state)  # GameStates are mutable, so be careful
    assert take_turn(state, turn) == ending_state


@mark.parametrize(
    "starting_state,ending_state",
    [
        (
            # land and 1-drop in play, rock and 2-drop available
            # we'll cast the 2-drop on turn 3 - on turn 2 it would be the rock
            GameState(
                ["Rock", "1 CMC"],
                CardBag({"2 CMC": 3, "Land": 3}),
                lands_in_play=1,
                cumulative_mana_in_play=1.0,
                compounded_mana_spent=1.0,
            ),
            GameState(
                ["1 CMC"],
                CardBag({"2 CMC": 2, "Rock": 1, "Land": 2}),
                lands_in_play=2,
                rocks_in_play=0,
                mana_available=0,
                cumulative_mana_in_play=3.0,
                compounded_mana_spent=4.0,
            ),
        ),
        (
            # 1-drop, 2 lands and a rock in play - cast the 4-drop
            # instead of the rock and the 3-drop, as we would on turn 3 or 4
            GameState(
                ["Rock", "1 CMC"],
                CardBag({"3 CMC": 1, "4 CMC": 1, "Land": 1}),
                lands_in_play=2,
                rocks_in_play=1,
                cumulative_mana_in_play=1.0,
                compounded_mana_spent=2.0,
            ),
            GameState(
                ["1 CMC"],
                CardBag({"3 CMC": 1, "Rock": 1}),
                lands_in_play=3,
                rocks_in_play=1,
                mana_available=0,
                cumulative_mana_in_play=5.0,
                compounded_mana_spent=7.0,
            ),
        ),
        (
            # Sol Ring and 3 rocks in play with 4-drop and 3-drop
            # cast a rock before the spells
            GameState(
                ["Rock", "1 CMC"],
                CardBag({"3 CMC": 1, "4 CMC": 1, "Land": 1}),
                lands_in_play=2,
                rocks_in_play=5,
            ),
            GameState(
                ["1 CMC"],
                CardBag({}),
                lands_in_play=3,
                rocks_in_play=6,
                mana_available=0,
                cumulative_mana_in_play=7.0,
                compounded_mana_spent=7.0,
            ),
        ),
        (
            # Sol Ring and 3 rocks in play with 1-drop, 4-drop and rock
            # cast all if there's nothing else to do with the mana
            # this is a real example from og runtime logs
            GameState(
                ["Rock", "1 CMC"],
                CardBag({"1 CMC": 1, "4 CMC": 1}),
                lands_in_play=2,
                rocks_in_play=5,
                cumulative_mana_in_play=15.2,
                compounded_mana_spent=25.4,
            ),
            GameState(
                ["1 CMC"],
                CardBag({}),
                lands_in_play=2,
                rocks_in_play=6,
                mana_available=1,
                cumulative_mana_in_play=20.2,
                compounded_mana_spent=approx(45.6),
            ),
        ),
        (
            # cast a 5-drop and a 6-drop
            # showing the extra value for 6-drops
            # also for coverage of the dumb duplicated code
            GameState(
                ["6 CMC", "Land"],
                CardBag({"5 CMC": 1, "Land": 1}),
                lands_in_play=3,
                rocks_in_play=7,
            ),
            GameState(
                ["Land"],
                CardBag({}),
                lands_in_play=4,
                rocks_in_play=7,
                mana_available=0,
                cumulative_mana_in_play=11.2,
                compounded_mana_spent=11.2,
            ),
        ),
    ],
)
@mark.parametrize("turn", [5, 6, 7])
def test_take_turn_five_or_more(starting_state, ending_state, turn):
    state = deepcopy(starting_state)  # GameStates are mutable, so be careful
    assert take_turn(state, turn) == ending_state
