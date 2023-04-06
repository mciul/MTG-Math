import logging
import random
from collections import defaultdict, UserDict
from dataclasses import dataclass, replace
from itertools import product
from typing import Dict, Generator, List, Tuple

logger = logging.getLogger()


CurveTuple = Tuple[int, int, int, int, int, int, int, int]


def nearby_values(start_value: int) -> Generator[int, None, None]:
    for value in range(max(start_value - 1, 0), start_value + 2):
        yield value


class CardBag(UserDict):
    def __setitem__(self, key: str, value: int):
        if value < 0:
            raise ValueError(f"Negative card count for {key}: {value}")
        if value > 0:
            super().__setitem__(key, value)
        elif key in self.data:
            # This happens all the time currently, should fix it eventually
            # logger.warning(f"Mutation: setting {key}=0 in {self}")
            self.pop(key)

    def __getitem__(self, key: str) -> int:
        return self.data.get(key, 0)

    def __add__(self, other: "CardBag") -> "CardBag":
        return CardBag(
            {
                card: self[card] + other[card]
                for card in self.keys() | other.keys()
            }
        )

    def __sub__(self, other: "CardBag") -> "CardBag":
        return CardBag(
            {card: max(0, count - other[card]) for card, count in self.items()}
        )

    def add(self, card: str, count: int) -> "CardBag":
        return CardBag({**self.data, card: self[card] + count})


@dataclass
class Curve:
    one: int
    two: int
    three: int
    four: int
    five: int
    six: int
    rock: int
    draw: int
    land: int

    @classmethod
    def fromtuple(cls, curve: CurveTuple) -> "Curve":
        one, two, three, four, five, six, rock, land = curve
        return cls(
            one=one,
            two=two,
            three=three,
            four=four,
            five=five,
            six=six,
            rock=rock,
            draw=0,
            land=land,
        )

    def astuple(self) -> CurveTuple:
        # ignore draw, currently it's always zero
        return (
            self.one,
            self.two,
            self.three,
            self.four,
            self.five,
            self.six,
            self.rock,
            self.land,
        )

    def copy(self) -> "Curve":
        return replace(self)

    @property
    def count(self):
        return sum(self.astuple())

    def distance_from(self, other: "Curve") -> int:
        return sum(
            abs(myvalue - othervalue)
            for myvalue, othervalue in zip(self.astuple(), other.astuple())
        )

    def nearby_decks(self) -> Generator["Curve", None, None]:
        ranges = (nearby_values(value) for value in self.astuple())
        for curve in product(*ranges):
            yield self.fromtuple(curve)

    @property
    def decklist(self) -> Dict[str, int]:
        return {
            "1 CMC": self.one,
            "2 CMC": self.two,
            "3 CMC": self.three,
            "4 CMC": self.four,
            "5 CMC": self.five,
            "6 CMC": self.six,
            "Rock": self.rock,
            "Sol Ring": 1,
            "Draw": self.draw,
            "Land": self.land,
        }

    def brief_desc(self) -> str:
        return (
            str(self.one)
            + ", "
            + str(self.two)
            + ", "
            + str(self.three)
            + ", "
            + str(self.four)
            + ", "
            + str(self.five)
            + ", "
            + str(self.six)
            + ", "
            + str(self.rock)
            + ", "
            + str(self.land)
        )

    def full_desc(self) -> str:
        return (
            str(self.one)
            + " one-drops, "
            + str(self.two)
            + " two, "
            + str(self.three)
            + " three, "
            + str(self.four)
            + " four, "
            + str(self.five)
            + " five, "
            + str(self.six)
            + " six, "
            + str(self.rock)
            + " Signet, 1 Sol Ring, "
            + str(self.land)
            + " lands "
        )


@dataclass
class GameState:
    """Tracks game state

    GameState is mutable - this is the sin of premature optimization

    For safety, mutation should only be done through methods
    """

    library: List[str]
    hand: CardBag
    lands_in_play: int = 0
    rocks_in_play: int = 0
    compounded_mana_spent: float = 0  # how does this relate to the below?
    cumulative_mana_in_play: float = 0  # WTF does this mean?
    mana_available: int = 0

    @classmethod
    def start(cls, decklist: CardBag) -> "GameState":
        library = []
        for card, count in decklist.items():
            library += [card] * count
        random.shuffle(library)
        hand = CardBag({})
        for _ in range(7):
            card = library.pop(0)
            hand = hand.add(card, 1)
        return cls(library, hand)

    def bottom_from_hand(self, selection: CardBag) -> None:
        """put cards from hand onto the bottom

        Actually, we just delete the cards, assuming we'll never get that
        far into the library

        Side effects: mutates game state by replacing hand
        """
        self.hand = self.hand - selection

    def untap(self) -> "GameState":
        self.mana_available = self.lands_in_play + self.rocks_in_play
        self.compounded_mana_spent += self.cumulative_mana_in_play
        return self

    def draw(self) -> str:
        """Update state by drawing 1 card from library to hand

        Returns the card drawn

        Side effects: mutates game state by replacing hand and mutating library
        """
        drawn = self.library.pop(0)
        self.hand = self.hand.add(drawn, 1)
        return drawn

    def play_from_hand(self, plays: CardBag) -> "GameState":
        """Update game state as if the card were played

        Side effects: mutates game state by replacing hand

        TODO: also update cards in play, mana spent, etc
        """
        self.hand -= plays
        self.lands_in_play += plays["Land"]
        self.mana_available += plays["Land"]
        self.rocks_in_play += plays["Rock"]
        self.mana_available -= plays["Rock"]
        self.rocks_in_play += 2 * plays["Sol Ring"]
        self.mana_available += plays["Sol Ring"]
        value_added = 0
        for cmc in range(1, 7):
            count = plays[f"{cmc} CMC"]
            self.mana_available -= count * cmc
            if cmc == 6:
                value_added += 6.2 * count
            else:
                value_added += cmc * count
        self.cumulative_mana_in_play += value_added
        self.compounded_mana_spent += value_added
        # TODO: raise exception for negative mana available?

        return self

    def add_to_hand(self, selection: CardBag):
        self.hand += selection


def do_we_keep(hand: CardBag, cards_to_keep: int, free: bool = False) -> bool:
    """Should we keep this hand or ship it?

    cards_to_keep tells us how many we can keep after bottoming
    free tells us if the next mulligan is free (we'll keep 7 again)
    """
    if cards_to_keep <= 4:
        return True
    min_lands = 3 if free else 2
    if hand["Sol Ring"] > 0:
        min_lands = 1
    max_lands = 5 if cards_to_keep > 5 else 6
    if cards_to_keep == 7:
        max_lands -= hand["Rock"]
    return min_lands <= hand["Land"] <= max_lands


def min_keep(hand: CardBag, card: str) -> int:
    """How many of the given card should not be put on the bottom"""
    if card == "Land":
        return 3 - hand["Sol Ring"] + max(0, hand["Rock"] - 3)
    if card == "Rock":
        if hand["Land"] >= 3 or hand["Rock"] >= 3:
            return 1
        return 2
    return 0


def cards_to_bottom(hand: CardBag, count: int) -> CardBag:
    descending_cmc = [f"{cmc} CMC" for cmc in range(6, 0, -1)]
    bottom = CardBag({})
    for card in ["Land", "Rock"] + descending_cmc:
        if count == 0:
            break
        bottomable = max(0, min(count, hand[card] - min_keep(hand, card)))
        bottom = bottom.add(card, bottomable)
        count -= bottomable
    return bottom


def take_turn(state: GameState, turn: int) -> GameState:
    # For turn_of_interest = 7, this range is {1, 2, ..., 7} so we
    # consider mana spent over the first 7 turns
    # compounded_mana_spent is what we return at the end
    # At the start of every turn, we add to it the sum of mana values of
    # all 1-drops, 2-drops, ..., 6-drops that we have cast thus far
    # During the turn, we add to it the mana value of any 1-drop, 2-drop,
    # ..., 6-drop we cast
    # Note that mana rocks or card draw spells don't count towards this

    state.untap()

    # In Commander, you always draw a card, even when playing first
    card_drawn = state.draw()

    # Play a land if possible
    land_played = False
    if state.hand["Land"] > 0:
        state.play_from_hand(CardBag({"Land": 1}))
        land_played = True

    mana_available_at_start_turn = state.mana_available
    we_cast_a_nonrock_spell_this_turn = False

    logger.debug(
        f"TURN {turn}. Card drawn {card_drawn}. {state.lands_in_play} "
        f"lands, {state.rocks_in_play} rocks. Mana available "
        f"{state.mana_available}. Cumulative mana {state.compounded_mana_spent}. "
        f"Hand: {state.hand}"
    )

    if turn == 1:
        if (state.mana_available >= 1) and state.hand["Sol Ring"] == 1:
            state.play_from_hand(CardBag({"Sol Ring": 1}))
            # Sol Ring counts as 2 mana rocks
            # Also cast Signet if possible
            if state.hand["Rock"] >= 1:
                state.play_from_hand(CardBag({"Rock": 1}))
            state.mana_available = 0
            # We can't do anything else after a turn one Sol Ring

    if turn >= 2:
        if (state.mana_available >= 1) and state.hand["Sol Ring"] == 1:
            state.play_from_hand(CardBag({"Sol Ring": 1}))
            # Costs one mana, immediately adds two. Card is utterly broken

    if turn == 2:
        Castable_rock = min(state.hand["Rock"], state.mana_available // 2)
        state.play_from_hand(CardBag({"Rock": Castable_rock}))
        # Rocks DO NOT count as mana spent or mana in play. Mana in play
        # represents creatures, planeswalkers, etc. Rocks are like lands

    # On turn 3 or 4, cast a mana rock and a (mana available - 1) drop if
    # possible
    if (
        turn in [3, 4]
        and state.mana_available >= 2
        and state.mana_available <= 7
    ):
        cmc_of_followup_spell = state.mana_available - 1
        if (
            state.hand["Rock"] >= 1
            and state.hand[f"{cmc_of_followup_spell} CMC"] >= 1
        ):
            state.play_from_hand(CardBag({"Rock": 1}))
            state.play_from_hand(CardBag({f"{cmc_of_followup_spell} CMC": 1}))
            we_cast_a_nonrock_spell_this_turn = True

    logger.debug(
        f"After rocks, mana available {state.mana_available}. Cumulative "
        f"mana {state.compounded_mana_spent}. Hand: {state.hand}"
    )

    if state.mana_available >= 3 and state.mana_available <= 6:
        if state.hand[f"{state.mana_available} CMC"] == 0:
            # We have, for example, 5 mana but don't have a 5-drop in hand
            # But let's check if we can cast a 2 and a 3 before checking
            # for 4s
            # Since mana_available - 2 could be 2, we also gotta check
            # if the cards are distinct
            second_cmc = state.mana_available - 2
            if (
                second_cmc != 2
                and state.hand["2 CMC"] >= 1
                and state.hand[f"{second_cmc} CMC"] >= 1
            ) or (second_cmc == 2 and state.hand["2 CMC"] >= 2):
                state.play_from_hand(CardBag({"2 CMC": 1}))
                state.play_from_hand(CardBag({f"{second_cmc} CMC": 1}))
                we_cast_a_nonrock_spell_this_turn = True

    for cmc in range(6, 0, -1):
        spell = f"{cmc} CMC"
        castable_count = min(state.hand[spell], state.mana_available // cmc)
        if castable_count > 0:
            state.play_from_hand(CardBag({spell: castable_count}))
            we_cast_a_nonrock_spell_this_turn = True

    Castable_rock = min(state.hand["Rock"], state.mana_available // 2)
    state.play_from_hand(CardBag({"Rock": Castable_rock}))

    # If we retroactively notice we could've snuck in a mana rock, do so
    if (
        (mana_available_at_start_turn >= 2 and state.mana_available == 1)
        and state.hand["Rock"] >= 1
        and we_cast_a_nonrock_spell_this_turn
    ):
        state.play_from_hand(CardBag({"Rock": 1}))

    logger.debug(
        f"After spells, mana available {state.mana_available}. Cumulative "
        f"mana {state.compounded_mana_spent}. Hand: {state.hand}"
    )
    return state
