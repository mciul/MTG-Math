import logging
import random
from functools import lru_cache
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
    """Represents a card and describes its behavior

    name is how we usually refer to cards - we often use name to look one up
    cmc will be deducted from mana available when cast
    mana_produced is mana that becomes available when the card is played
      - mana that becomes available on untap is handled elsewhere
    value represents mana in play, but only for creatures, etc.
     - Rocks are treated as though they had no intrinsic value
    effect is a strategy that gets called when the card is played
     - e.g. where lands_in_play gets updated, which provides mana on untap
     - updating value and adding available mana are handled separately
       and should not be included in the effectjjjj

    This framework would allow us to easily add new card types, such as draw
    """

    name: str
    cmc: int
    mana_produced: int
    value: float
    effect: Callable[["GameState", int], "GameState"]


def no_effect(state: "GameState", count: int) -> "GameState":
    return state


def add_land(state: "GameState", count: int) -> "GameState":
    return state.play_land(count)


def add_rocks(state: "GameState", count: int) -> "GameState":
    return state.play_rocks(count)


def add_sol_ring(state: "GameState", count: int) -> "GameState":
    return state.play_rocks(count * 2)


CARD_TYPES: List[Card] = [
    Card("Land", 0, 1, 0.0, add_land),
    Card("Sol Ring", 1, 2, 0.0, add_sol_ring),
    Card("Rock", 2, 1, 0.0, add_rocks),
    Card("1 CMC", 1, 0, 1.0, no_effect),
    Card("2 CMC", 2, 0, 2.0, no_effect),
    Card("3 CMC", 3, 0, 3.0, no_effect),
    Card("4 CMC", 4, 0, 4.0, no_effect),
    Card("5 CMC", 5, 0, 5.0, no_effect),
    Card("6 CMC", 6, 0, 6.2, no_effect),
]

CARD_NAMES = [card.name for card in CARD_TYPES]
CARDS: Dict[str, Card] = {card.name: card for card in CARD_TYPES}

CARDS_BY_CMC: Dict[int, str] = defaultdict(
    str, {card.cmc: card.name for card in CARDS.values() if card.cmc > 0}
)


def spells_in_descending_order(max_cmc: int = 6) -> List[str]:
    return [CARDS_BY_CMC[cmc] for cmc in range(max_cmc, 0, -1)]


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

    def __hash__(self) -> int:
        return hash((tuple(self[name] for name in CARD_NAMES)))

    def add(self, card: str, count: int) -> "CardBag":
        """return a Cardbag with the card count increased

        we will return a mutated version of self here because
        creating a new CardBag is slow. So be cautious...
        """
        self[card] += count
        return self

    def net_mana_cost(self) -> int:
        cost = 0
        for name, count in self.items():
            card = CARDS[name]
            cost += card.cmc * count
            cost -= card.mana_produced * count
        return cost

    def includes_nonrock(self) -> bool:
        return any(
            CARDS[name].mana_produced == 0 for name, count in self.items()
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

    library is a list with the to card at index 0

    hand, lands_in_play, and rocks_in_play are about what they sound like
    (but a Sol Ring is represented by two rocks)

    compounded_mana_spent is what we return at the end
    At the start of every turn, we add to it the sum of mana values of
    all 1-drops, 2-drops, ..., 6-drops that we have cast thus far
    During the turn, we add to it the mana value of any 1-drop, 2-drop,
    ..., 6-drop we cast

    cumulative_mana_in_play represents all the mana we've spent to advance
    the board state (mana rocks or card draw spells don't count towards this)
    It's not used directly, just an intermediate value to calculate
    compounding

    mana_available represents untapped mana available for the turn
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
        # random.shuffle(library)
        # shuffling seems to take a lot of time, but we only need 14
        # cards to play a game - what if we only take 14?
        library = random.sample(library, 14)
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
        - replaces  hand
        - updates mana available
        - calls arbitrary methods based on card effect,
          many of which have side effects

        Returns a game state so in theory it could create a new one
        without mutating. That would probably be slow though.

        For some reason mutating the hand turned out to be even slower
        than replacing it... not sure why
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

    def add_to_hand(self, selection: CardBag) -> "GameState":
        self.hand += selection
        return self


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


def mana_left_for(mana_available: int, play: CardBag) -> int:
    return mana_available - play.net_mana_cost()


def max_playable(card: Card, in_hand: int, mana_available: int) -> int:
    if card.cmc == 0:  # Land
        return min(1, in_hand)
    return min(in_hand, mana_available // card.cmc)


def castable_count_for(
    hand: CardBag, play: CardBag, card_name: str, starting_mana: int
) -> int:
    in_hand = hand[card_name] - play[card_name]
    if in_hand < 1:
        return 0
    mana_available = mana_left_for(starting_mana, play)
    card = CARDS[card_name]
    if card.mana_produced == 1 and play.includes_nonrock():
        # maybe we can cast an extra rock before casting the nonrock spell
        mana_available += 1
    # note - no protection against divide-by-zero (should never happen)
    return max_playable(card, in_hand, mana_available)


def play_one_rock_before_spell(
    hand: CardBag, starting_mana: int, play: CardBag, optimal_spells: List[str]
) -> CardBag:
    """Play one rock if we can max out the remaining mana on a spell

    We still want to ramp a bit, but keep it in check if we have a spell
    we can play with all the remaining mana
    """
    if len(optimal_spells) < 2:
        # there is no such spell with CMC = mana_available - 1
        return play

    if castable_count_for(hand, play, optimal_spells[1], starting_mana) < 1:
        # we don't have it in hand
        return play
    # cast one rock now, we'll cast the spell later
    castable_rock = min(
        1, castable_count_for(hand, play, "Rock", starting_mana)
    )
    return play.add("Rock", castable_rock)


def play_two_drop_as_first_spell(
    hand: CardBag, starting_mana: int, play: CardBag, optimal_spells: List[str]
) -> CardBag:
    """play a two-drop if if we can't use all our mana on one big spell
    We prefer to double-spell with a two-drop rather than a one-drop,
    which is handled elsewhere
    """
    # double-spelling with a 1-drop
    if len(optimal_spells) < 3:
        # there is no such spell with CMC = available mana - 2
        return play
    if castable_count_for(hand, play, optimal_spells[0], starting_mana) > 0:
        # just cast the big one
        return play
    if castable_count_for(hand, play, "2 CMC", starting_mana) < 1:
        # we don't have da 2 drop
        return play
    hypothetical = play.copy().add("2 CMC", 1)
    if (
        castable_count_for(
            hand, hypothetical, optimal_spells[2], starting_mana
        )
        < 1
    ):
        # we can't cast the second spell
        return play
    # ok, let's do it
    return hypothetical


@lru_cache(maxsize=32768)
def choose_play_for(hand: CardBag, mana_available: int, turn: int) -> CardBag:
    play = CardBag({"Land": min(1, hand["Land"])})

    play = play.add(
        "Sol Ring",
        castable_count_for(hand, play, "Sol Ring", mana_available),
    )

    if turn < 3:
        # early on, play lots of rocks
        play = play.add(
            "Rock",
            castable_count_for(hand, play, "Rock", mana_available),
        )

    if turn == 1 and play["Sol Ring"] > 0:
        # According to Frank Karsten's article, we can't cast nonrock spells
        # on Turn 1 if we played a Sol Ring
        return play

    optimal_spells = spells_in_descending_order(
        mana_left_for(mana_available, play)
    )

    if turn in [3, 4]:
        play = play_one_rock_before_spell(
            hand, mana_available, play, optimal_spells
        )

    if mana_left_for(mana_available, play) <= 6:
        play = play_two_drop_as_first_spell(
            hand, mana_available, play, optimal_spells
        )

    for spell in optimal_spells + ["Rock"]:
        play = play.add(
            spell, castable_count_for(hand, play, spell, mana_available)
        )

    return play


def choose_play(state: GameState, turn: int) -> CardBag:
    simplified_turn = 3 if turn == 4 else min(turn, 5)
    return choose_play_for(state.hand, state.mana_available, simplified_turn)


def take_turn(state: GameState, turn: int) -> GameState:
    state.untap()

    # In Commander, you always draw a card, even when playing first
    card_drawn = state.draw()

    # I think maybe f-strings in logger statements slow us down
    logger.debug(
        "TURN %d. Card drawn %s. %d lands, %d rocks. Mana available %d. "
        "Cumulative mana %d. Hand: %s",
        turn,
        card_drawn,
        state.lands_in_play,
        state.rocks_in_play,
        state.mana_available,
        state.compounded_mana_spent,
        state.hand,
    )

    state = state.play_from_hand(choose_play(state, turn))

    logger.debug(
        "After spells, mana available %d. Cumulative mana %d. Hand: %s",
        state.mana_available,
        state.compounded_mana_spent,
        state.hand,
    )

    return state
