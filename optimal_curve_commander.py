from typing import Generator, Tuple, Dict, Union, List
from itertools import product
import random
import logging

from mtg_math.curve_sim import (
    nearby_values,
    CurveTuple,
    CardBag,
    Curve,
    GameState,
    do_we_keep,
    cards_to_bottom,
)

logger = logging.getLogger()
# to enable debug:
logging.basicConfig(level=logging.INFO)

# Manually adjust these parameters to set the deck type and an initial guess
# for where to start searching
# The card values should sum to 98 because we're always adding a Sol Ring
# Note that the simulation code allows for card draw spells, but these were
# now fixed at 0 in the optimization because early tests never favored them
commander_costs = [2, 4]
deck_size = 100 - len(commander_costs)
initial_rock = 10
initial_1_cmc = 7
initial_2_cmc = 10
initial_3_cmc = 10
initial_4_cmc = 14
initial_5_cmc = 9
initial_6_cmc = 0
initial_land = 38
initial_draw = 0

# num_simulations = 10000
# initial_num_simulations = 100
# target_num_simulations = 200000
target_num_simulations = 2000
initial_num_simulations = target_num_simulations // 20


initial_curve = Curve(
    one=initial_1_cmc,
    two=initial_2_cmc,
    three=initial_3_cmc,
    four=initial_4_cmc,
    five=initial_5_cmc,
    six=initial_6_cmc,
    rock=initial_rock,
    draw=initial_draw,
    land=initial_land,
)


def shuffle_and_take_mulligans(decklist: CardBag) -> GameState:
    """Return the game state after finally keeping a hand"""
    for handsize, free in zip([7, 7, 6, 5, 4], [True] + [False] * 4):
        state = GameState.start(decklist)
        logger.debug(f"Opening hand: {state.hand}")
        if do_we_keep(state.hand, handsize, free):
            logger.debug(f"Keeping opening hand with {handsize} cards")
            state.bottom_from_hand(cards_to_bottom(state.hand, 7 - handsize))
            logger.debug(f"After bottoming: {state.hand}")
            return state
        logger.debug(f"Not keeping {handsize} cards - mulliganing")
    raise RuntimeError("We should never mulligan a 4-card hand")


def add_commanders(state: GameState, commander_costs: List[int]) -> GameState:
    """Put commanders in the game's 'hand'"""
    state = shuffle_and_take_mulligans(decklist)
    commanders = CardBag({})
    for commander_cost in commander_costs:
        commanders.add(f"{commander_cost} CMC", 1)
    state.add_to_hand(commanders)
    return state


def run_one_sim(
    decklist: CardBag, commander_costs: List[int]
) -> Tuple[float, int]:
    # Initialize variables
    lands_in_play = 0
    rocks_in_play = 0
    compounded_mana_spent = 0
    cumulative_mana_in_play = 0
    turn_of_interest = 7
    mana_available = 0
    draw_cost = 4  # Cost is 3 for Divination, 4 for Harmonize
    draw_draw = 3  # Draw is 2 for Divination, 3 for Harmonize

    # Draw opening hands and mulligan
    logger.debug("----------")
    state = shuffle_and_take_mulligans(decklist)
    state = add_commanders(state, commander_costs)
    logger.debug(f"After adding commander: {state.hand}")

    for turn in range(1, turn_of_interest + 1):
        # For turn_of_interest = 7, this range is {1, 2, ..., 7} so we
        # consider mana spent over the first 7 turns
        # compounded_mana_spent is what we return at the end
        # At the start of every turn, we add to it the sum of mana values of
        # all 1-drops, 2-drops, ..., 6-drops that we have cast thus far
        # During the turn, we add to it the mana value of any 1-drop, 2-drop,
        # ..., 6-drop we cast
        # Note that mana rocks or card draw spells don't count towards this

        compounded_mana_spent += cumulative_mana_in_play

        # In Commander, you always draw a card, even when playing first
        card_drawn = state.draw()
        hand = state.hand

        # Play a land if possible
        land_played = False
        if hand["Land"] > 0:
            hand["Land"] -= 1
            lands_in_play += 1
            land_played = True

        mana_available = lands_in_play + rocks_in_play
        mana_available_at_start_turn = mana_available
        we_cast_a_nonrock_spell_this_turn = False

        logger.debug(
            f"TURN {turn}. Card drawn {card_drawn}. {lands_in_play} "
            f"lands, {rocks_in_play} rocks. Mana available "
            f"{mana_available}. Cumulative mana {compounded_mana_spent}. "
            f"Hand: {hand}"
        )

        if turn == 1:
            lucky = 1 if hand["Sol Ring"] == 1 else 0
            if (mana_available >= 1) and hand["Sol Ring"] == 1:
                hand["Sol Ring"] -= 1
                # Sol Ring counts as 2 mana rocks
                rocks_in_play += 2
                # Also cast Signet if possible
                if hand["Rock"] >= 1:
                    hand["Rock"] -= 1
                    rocks_in_play += 1
                mana_available = 0
                # We can't do anything else after a turn one Sol Ring

        if turn >= 2:
            if (mana_available >= 1) and hand["Sol Ring"] == 1:
                hand["Sol Ring"] -= 1
                # Costs one mana, immediately adds two. Card is utterly broken
                mana_available += 1
                rocks_in_play += 2

        if turn == 2:
            Castable_rock = min(hand["Rock"], mana_available // 2)
            hand["Rock"] -= Castable_rock
            # Rocks cost 2 each, then tap for 1 each
            mana_available -= Castable_rock * 2
            mana_available += Castable_rock
            rocks_in_play += Castable_rock
            # Rocks DO NOT count as mana spent or mana in play. Mana in play
            # represents creatures, planeswalkers, etc. Rocks are like lands

        # On turn 3 or 4, cast a mana rock and a (mana available - 1) drop if
        # possible
        if turn in [3, 4] and mana_available >= 2 and mana_available <= 7:
            cmc_of_followup_spell = mana_available - 1
            if hand["Rock"] >= 1 and hand[f"{cmc_of_followup_spell} CMC"] >= 1:
                hand["Rock"] -= 1
                mana_available -= 1
                rocks_in_play += 1
                hand[f"{cmc_of_followup_spell} CMC"] -= 1
                mana_available -= cmc_of_followup_spell
                compounded_mana_spent += cmc_of_followup_spell
                cumulative_mana_in_play += cmc_of_followup_spell
                we_cast_a_nonrock_spell_this_turn = True

        logger.debug(
            f"After rocks, mana available {mana_available}. Cumulative "
            f"mana {compounded_mana_spent}. Hand: {hand}"
        )

        if mana_available >= 3 and mana_available <= 6:
            if hand[f"{mana_available} CMC"] == 0:
                # We have, for example, 5 mana but don't have a 5-drop in hand
                # But let's check if we can cast a 2 and a 3 before checking
                # for 4s
                # Since mana_available - 2 could be 2, we also gotta check
                # if the cards are distinct
                if (
                    mana_available - 2 != 2
                    and hand["2 CMC"] >= 1
                    and hand[f"{mana_available - 2} CMC"] >= 1
                ) or (mana_available - 2 == 2 and hand["2 CMC"] >= 2):
                    hand["2 CMC"] -= 1
                    hand[f"{mana_available - 2} CMC"] -= 1
                    compounded_mana_spent += mana_available
                    cumulative_mana_in_play += mana_available
                    mana_available = 0
                    we_cast_a_nonrock_spell_this_turn = True

        Castable_cmc_6 = min(hand["6 CMC"], mana_available // 6)
        hand["6 CMC"] -= Castable_cmc_6
        mana_available -= Castable_cmc_6 * 6
        # Six drops are very powerful and count as 6.2 mana each
        compounded_mana_spent += Castable_cmc_6 * 6.2
        cumulative_mana_in_play += Castable_cmc_6 * 6.2

        Castable_cmc_5 = min(hand["5 CMC"], mana_available // 5)
        hand["5 CMC"] -= Castable_cmc_5
        mana_available -= Castable_cmc_5 * 5
        compounded_mana_spent += Castable_cmc_5 * 5
        cumulative_mana_in_play += Castable_cmc_5 * 5

        Castable_cmc_4 = min(hand["4 CMC"], mana_available // 4)
        hand["4 CMC"] -= Castable_cmc_4
        mana_available -= Castable_cmc_4 * 4
        compounded_mana_spent += Castable_cmc_4 * 4
        cumulative_mana_in_play += Castable_cmc_4 * 4

        Castable_cmc_3 = min(hand["3 CMC"], mana_available // 3)
        hand["3 CMC"] -= Castable_cmc_3
        mana_available -= Castable_cmc_3 * 3
        compounded_mana_spent += Castable_cmc_3 * 3
        cumulative_mana_in_play += Castable_cmc_3 * 3

        Castable_cmc_2 = min(hand["2 CMC"], mana_available // 2)
        hand["2 CMC"] -= Castable_cmc_2
        mana_available -= Castable_cmc_2 * 2
        compounded_mana_spent += Castable_cmc_2 * 2
        cumulative_mana_in_play += Castable_cmc_2 * 2

        Castable_cmc_1 = min(hand["1 CMC"], mana_available // 1)
        hand["1 CMC"] -= Castable_cmc_1
        mana_available -= Castable_cmc_1 * 1
        compounded_mana_spent += Castable_cmc_1 * 1
        cumulative_mana_in_play += Castable_cmc_1 * 1

        Castable_rock = min(hand["Rock"], mana_available // 2)
        hand["Rock"] -= Castable_rock
        mana_available -= Castable_rock * 2
        mana_available += Castable_rock
        rocks_in_play += Castable_rock

        if (
            Castable_cmc_6 >= 1
            or Castable_cmc_5 >= 1
            or Castable_cmc_4 >= 1
            or Castable_cmc_3 >= 1
            or Castable_cmc_2 >= 1
            or Castable_cmc_1 >= 1
        ):
            we_cast_a_nonrock_spell_this_turn = True

        # If we retroactively notice we could've snuck in a mana rock, do so
        if (
            (mana_available_at_start_turn >= 2 and mana_available == 1)
            and hand["Rock"] >= 1
            and we_cast_a_nonrock_spell_this_turn
        ):
            hand["Rock"] -= 1
            rocks_in_play += 1

        # Finally, cast card draw spells
        if draw_cost <= mana_available and hand["Draw"] >= 1:
            hand["Draw"] -= 1
            mana_available -= draw_cost
            for _ in range(draw_draw):
                card_drawn = library.pop(0)
                hand[card_drawn] += 1
            if not land_played and hand["Land"] >= 1:
                hand["Land"] -= 1
                lands_in_play += 1
                mana_available += 1
                land_played = True
        # I tried some code to cast spells after a card drawer, but it was
        # all to no avail as card draw spells were never chosen by the
        # optimizer regardless
        # So I deleted that entire part of the code for now

        logger.debug(
            f"After spells, mana available {mana_available}. Cumulative "
            f"mana {compounded_mana_spent}. Hand: {hand}"
        )

    # Return lucky (True if you had Sol Ring on turn 1) to enable better rare
    # event simulation with reduced variance, although that part was cut for
    # time reasons
    return (compounded_mana_spent, lucky)


# Initialize local search algorithm
best_curve = initial_curve.copy()
previous_best_mana_spent = 0
previous_sims_for_best_deck = 0
sims_for_best_deck = 0
continue_searching = True

# We'll store and update the results for various decks in two dictionaries
Estimation = {}
Number_sims = {}

# Start the local search
# We start at a given initial feasible solution and we keep moving to better
# points in a neighborhood until no better point exists.
# Then we have reached a local optimum. We need a certain number of
# simulations before we can "safely" stop.
# Neighborhood of a deck X, when the last nr sims for the best deck is <
# 150000:
# all possible decks where the sum of the the absolute values of the
# difference with X is at most one.
# Neighborhood of a deck X, when the last nr sims for the best deck is:
# all possible 99-card decks where the for each card type, the absolute
# values of the difference with the number of copies of that card type in X
# is at most one.
# We start with a limited number of simulations
# (num_simulations, 3000) as we explore and increase the number of
# simulations in every step
# If we have to re-evaluate a deck, we combine the simulations from the
# current iterations with the ones that have already taken place prior.


num_simulations = initial_num_simulations
while continue_searching:
    best_mana_spent = 0
    improvement_possible = False

    for curve in best_curve.nearby_decks():
        nr_changes = curve.distance_from(best_curve)
        if previous_sims_for_best_deck < target_num_simulations * 3 // 4:
            in_neighborhood = curve.count == deck_size - 1 and nr_changes <= 2
        else:
            in_neighborhood = curve.count == deck_size - 1
        # Note that we check for deck_size -1
        # because Sol Ring is always part of
        # the deck

        if in_neighborhood:
            decklist = curve.decklist

            if curve.astuple() not in Estimation.keys():
                Estimation[curve.astuple()] = 0
            if (curve.astuple()) not in Number_sims.keys():
                Number_sims[curve.astuple()] = 0

            # If we know from previous
            # iterations that this deck is
            # performing not even close to
            # the best deck, then don't waste
            # more sims
            dont_bother = False
            if (
                Number_sims[curve.astuple()] > target_num_simulations // 4
                and Estimation[curve.astuple()]
                < 0.998 * previous_best_mana_spent
            ):
                dont_bother = True
            if (
                Number_sims[curve.astuple()] > target_num_simulations // 2
                and Estimation[curve.astuple()]
                < 0.999 * previous_best_mana_spent
            ):
                dont_bother = True
            if (
                Number_sims[curve.astuple()] > target_num_simulations
                and Estimation[curve.astuple()]
                < 0.9995 * previous_best_mana_spent
            ):
                dont_bother = True

            if not dont_bother:
                total_mana_spent = 0.0
                for _ in range(num_simulations):
                    (mana_spent_in_sim, lucky) = run_one_sim(
                        decklist, commander_costs
                    )
                    # Lucky is true for Sol Ring on turn 1. This
                    # could be used for clever variance
                    # reduction techniques
                    # But this part was cut for time reasons
                    total_mana_spent += mana_spent_in_sim
                average_mana_spent = round(
                    total_mana_spent / num_simulations,
                    4,
                )
                # Add previous total sims to
                # current number sims
                previous_total_sims = Number_sims[curve.astuple()]
                Number_sims[curve.astuple()] += num_simulations
                # Take nr_sim-weighted combination of previous
                # estimation and current estimation
                previous_estimate = Estimation[curve.astuple()]
                Estimation[curve.astuple()] = round(
                    (
                        previous_estimate * previous_total_sims
                        + average_mana_spent * num_simulations
                    )
                    / Number_sims[curve.astuple()],
                    4,
                )

                current_deck_is_same_as_previous_best = curve == best_curve

                # Are we doing better than
                # the previuos best deck?
                if Estimation[curve.astuple()] >= best_mana_spent:
                    firstword = (
                        "Update!"
                        if current_deck_is_same_as_previous_best
                        else "Improv!"
                        if Estimation[curve.astuple()]
                        >= previous_best_mana_spent
                        else "-------"
                    )
                    print(
                        "---"
                        + firstword
                        + "Deck "
                        + curve.brief_desc()
                        + " had "
                        + str(previous_estimate)
                        + "/"
                        + str(int(previous_total_sims))
                        + ", now "
                        + str(Estimation[curve.astuple()])
                        + "/"
                        + str(int(Number_sims[curve.astuple()]))
                    )
                    best_mana_spent = Estimation[curve.astuple()]
                    new_best_curve = curve.copy()
                    sims_for_best_deck = Number_sims[curve.astuple()]
                elif (
                    Estimation[curve.astuple()] < previous_best_mana_spent
                    and Estimation[curve.astuple()] > 0.998 * best_mana_spent
                ):
                    firstword = (
                        "Update!"
                        if current_deck_is_same_as_previous_best
                        else "Close! "
                    )
                    print(
                        "---"
                        + firstword
                        + "Deck "
                        + curve.brief_desc()
                        + " had "
                        + str(previous_estimate)
                        + "/"
                        + str(int(previous_total_sims))
                        + ", now "
                        + str(Estimation[curve.astuple()])
                        + "/"
                        + str(int(Number_sims[curve.astuple()]))
                    )

    previous_still_best = new_best_curve == best_curve
    previous_best_mana_spent = best_mana_spent
    if previous_still_best and sims_for_best_deck > target_num_simulations:
        continue_searching = False
    else:
        continue_searching = True

    # Move to the best option we've seen in the immediate neighborhood
    best_curve = new_best_curve

    # However, check if we've seen a better option with reasonable sample
    # size in previous iterations; if so, override
    for curve_data in Estimation.keys():
        curve = Curve.fromtuple(curve_data)
        if (
            Estimation[curve.astuple()] >= best_mana_spent
            and Number_sims[curve.astuple()] >= previous_sims_for_best_deck / 2
        ):
            best_mana_spent = Estimation[curve.astuple()]
            best_curve = curve
            sims_for_best_deck = Number_sims[curve.astuple()]

    num_simulations += initial_num_simulations // 10
    previous_sims_for_best_deck = sims_for_best_deck
    print(
        "====>Deck: "
        + curve.full_desc()
        + " ==> "
        + str(best_mana_spent)
        + "."
    )
