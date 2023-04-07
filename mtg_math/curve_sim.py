import logging
import random
from collections import defaultdict, UserDict
from dataclasses import dataclass, replace
from itertools import product
from typing import Dict, Generator, List, Tuple, Callable

logger = logging.getLogger()


CurveTuple = Tuple[int, int, int, int, int, int, int, int]


def nearby_values(start_value: int) -> Generator[int, None, None]:
    for value in range(max(start_value - 1, 0), start_value + 2):
        yield value


@dataclass
class Card:
    name: str
    cmc: int
    mana_produced: int
    value: float
    effect: Callable[["GameState", int], "GameState"]


# Rocks DO NOT count as mana spent or mana in play. Mana in play
# represents creatures, planeswalkers, etc. Rocks are like lands
# We represent mana in play with the "value" attribute


def no_effect(state: "GameState", count: int) -> "GameState":
    return state


def add_land(state: "GameState", count: int) -> "GameState":
    return state.play_land(count)


def add_rocks(state: "GameState", count: int) -> "GameState":
    return state.play_rocks(count)


def add_sol_ring(state: "GameState", count: int) -> "GameState":
    return state.play_rocks(count * 2)


CARDS: Dict[str, Card] = {
    "Land": Card("Land", 0, 1, 0.0, add_land),
    "Sol Ring": Card("Sol Ring", 1, 2, 0.0, add_sol_ring),
    "Rock": Card("Rock", 2, 1, 0.0, add_rocks),
    "1 CMC": Card("1 CMC", 1, 0, 1.0, no_effect),
    "2 CMC": Card("2 CMC", 2, 0, 2.0, no_effect),
    "3 CMC": Card("3 CMC", 3, 0, 3.0, no_effect),
    "4 CMC": Card("4 CMC", 4, 0, 4.0, no_effect),
    "5 CMC": Card("5 CMC", 5, 0, 5.0, no_effect),
    "6 CMC": Card("6 CMC", 6, 0, 6.2, no_effect),
}

CARDS_BY_CMC: Dict[int, str] = defaultdict(
    str, {card.cmc: card.name for card in CARDS.values() if card.cmc > 0}
)


def spells_in_descending_order() -> List[str]:
    return [CARDS_BY_CMC[cmc] for cmc in range(6, 0, -1)]


# now it wouldn't be too hard to model draw effects!


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

    def net_mana_cost(self) -> int:
        cost = 0
        for name, count in self.items():
            card = CARDS[name]
            cost += card.cmc * count
            cost -= card.mana_produced * count
        return cost

    def includes_nonrock(self) -> bool:
        return any(
            CARDS[name].mana_produced == 0
            for name, count in self.items()
            if count > 0
        )


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

    def play_land(self, count: int) -> "GameState":
        self.lands_in_play += count
        return self

    def play_rocks(self, count: int) -> "GameState":
        self.rocks_in_play += count
        return self

    def add_value(self, value: float) -> "GameState":
        self.cumulative_mana_in_play += value
        self.compounded_mana_spent += value
        return self

    def play_from_hand(self, plays: CardBag) -> "GameState":
        """Update game state as if the card were played

        Side effects: mutates game state
        - replaces hand
        - updates mana available
        - calls arbitrary methods based on card effect,
          many of which have side effects

        Returns a game state so in theory it could create a new one
        without mutating. That would probably be slow though.
        """
        self.hand -= plays
        new_state = self
        for name, count in plays.items():
            card = CARDS[name]
            self.mana_available -= card.cmc * count
            self.mana_available += card.mana_produced * count
            new_state = card.effect(new_state, count)
            new_state = new_state.add_value(card.value * count)
        # TODO: raise exception for negative mana available?

        return new_state

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
    bottom = CardBag({})
    for card in ["Land", "Rock"] + spells_in_descending_order():
        if count == 0:
            break
        bottomable = max(0, min(count, hand[card] - min_keep(hand, card)))
        bottom = bottom.add(card, bottomable)
        count -= bottomable
    return bottom


def mana_left(state: GameState, play: CardBag) -> int:
    return state.mana_available - play.net_mana_cost()


def castable_count(state: GameState, play: CardBag, card_name: str) -> int:
    """how many of `card_name` can we play if we've already made `play`

    don't consider mana available after playing the first one, just
    use the currently available mana
    """
    hand = state.hand - play
    if card_name not in hand.keys():
        return 0
    card = CARDS[card_name]
    # note - no protection against divide-by-zero (should never happen)
    return min(hand[card_name], mana_left(state, play) // card.cmc)


def choose_play(state: GameState, turn: int) -> CardBag:
    play = CardBag({"Land": min(1, state.hand["Land"])})

    mana_available_at_start_turn = state.mana_available

    play = play.add("Sol Ring", castable_count(state, play, "Sol Ring"))
    if turn < 3:
        # early on, play lots of rocks
        play = play.add("Rock", castable_count(state, play, "Rock"))

    if turn == 1 and play["Sol Ring"] > 0:
        # According to Frank Karsten's article, we can only play rocks
        # on Turn 1 if we play a Sol Ring
        return play

    # On turn 3 or 4, cast a mana rock and a (mana available - 1) drop if
    # possible
    if turn in [3, 4]:
        cmc_of_followup_spell = mana_left(state, play) - 1
        spell = CARDS_BY_CMC[cmc_of_followup_spell]
        if castable_count(state, play, spell) >= 1:
            play = play.add("Rock", castable_count(state, play, "Rock"))

    logger.debug(
        f"After rocks, mana available {state.mana_available}. Cumulative "
        f"mana {state.compounded_mana_spent}. Hand: {state.hand}"
    )

    if 3 <= mana_left(state, play) <= 6:
        remaining_cards = state.hand - play
        spell = CARDS_BY_CMC[mana_left(state, play)]
        if remaining_cards[spell] == 0:
            # We have, for example, 5 mana but don't have a 5-drop in hand
            # But let's check if we can cast a 2 and a 3 before checking
            # for 4s
            # Since mana_available - 2 could be 2, we also gotta check
            # if the cards are distinct
            second_cmc = mana_left(state, play) - 2
            second_spell = CARDS_BY_CMC[second_cmc]
            if (
                second_cmc != 2
                and remaining_cards["2 CMC"] >= 1
                and remaining_cards[second_spell] >= 1
            ) or (second_cmc == 2 and remaining_cards["2 CMC"] >= 2):
                play = play + CardBag({"2 CMC": 1, second_spell: 1})

    for spell in spells_in_descending_order():
        if castable_count(state, play, spell) > 0:
            play = play.add(spell, castable_count(state, play, spell))

    play = play.add("Rock", castable_count(state, play, "Rock"))

    # If we retroactively notice we could've snuck in a mana rock, do so
    remaining_cards = state.hand - play
    if (
        (mana_available_at_start_turn >= 2 and mana_left(state, play) == 1)
        and remaining_cards["Rock"] >= 1
        and play.includes_nonrock()
    ):
        play = play.add("Rock", 1)
    return play


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

    logger.debug(
        f"TURN {turn}. Card drawn {card_drawn}. {state.lands_in_play} "
        f"lands, {state.rocks_in_play} rocks. Mana available "
        f"{state.mana_available}. Cumulative mana {state.compounded_mana_spent}. "
        f"Hand: {state.hand}"
    )

    state = state.play_from_hand(choose_play(state, turn))
    logger.debug(
        f"After spells, mana available {state.mana_available}. Cumulative "
        f"mana {state.compounded_mana_spent}. Hand: {state.hand}"
    )
    return state
