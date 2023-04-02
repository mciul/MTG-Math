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
        super().__setitem__(key, value)

    def __getitem__(self, key: str) -> int:
        return self.data.get(key, 0)

    def __sub__(self, other: "CardBag") -> "CardBag":
        return CardBag(
            {card: count - other[card] for card, count in self.items()}
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


class GameState:
    def __init__(self, library: List[str], hand: CardBag):
        self.library = library
        self.hand = hand

    @classmethod
    def start(cls, decklist: CardBag) -> "GameState":
        library = []
        for card, count in decklist.items():
            library += [card] * count
        random.shuffle(library)
        hand: CardBag = defaultdict(int)
        for _ in range(7):
            card = library.pop(0)
            hand[card] += 1
        return cls(library, hand)

    def bottom_from_hand(self, selection: CardBag):
        """put cards from hand onto the bottom

        Actually, we just delete the cards, assuming we'll never get that
        far into the library
        """
        self.hand = self.hand - selection


def nr_mana(hand: CardBag) -> int:
    return hand.get("Land", 0) + hand.get("Rock", 0)


def nr_spells(hand: CardBag) -> int:
    return (
        hand["1 CMC"]
        + hand["2 CMC"]
        + hand["3 CMC"]
        + hand["4 CMC"]
        + hand["5 CMC"]
        + hand["6 CMC"]
        + hand["Rock"]
        + hand["Draw"]
    )


def put_spells_on_bottom(
    hand: CardBag, spells_remaining_to_bottom: int
) -> CardBag:
    # If the hand has too much mana, the first card(s) to bottom are all but one Rock
    hand = hand.copy()
    if (hand["Rock"] >= 3) or (hand["Land"] >= 3 and hand["Rock"] >= 2):
        Bottomable_rock = min(hand["Rock"] - 1, spells_remaining_to_bottom)
        hand["Rock"] -= Bottomable_rock
        spells_remaining_to_bottom -= Bottomable_rock

    Bottomable_cmc_6 = min(hand["6 CMC"], spells_remaining_to_bottom)
    hand["6 CMC"] -= Bottomable_cmc_6
    spells_remaining_to_bottom -= Bottomable_cmc_6

    Bottomable_cmc_5 = min(hand["5 CMC"], spells_remaining_to_bottom)
    hand["5 CMC"] -= Bottomable_cmc_5
    spells_remaining_to_bottom -= Bottomable_cmc_5

    Bottomable_cmc_4 = min(hand["4 CMC"], spells_remaining_to_bottom)
    hand["4 CMC"] -= Bottomable_cmc_4
    spells_remaining_to_bottom -= Bottomable_cmc_4

    Bottomable_cmc_3 = min(hand["3 CMC"], spells_remaining_to_bottom)
    hand["3 CMC"] -= Bottomable_cmc_3
    spells_remaining_to_bottom -= Bottomable_cmc_3

    Bottomable_cmc_2 = min(hand["2 CMC"], spells_remaining_to_bottom)
    hand["2 CMC"] -= Bottomable_cmc_2
    spells_remaining_to_bottom -= Bottomable_cmc_2

    Bottomable_cmc_1 = min(hand["1 CMC"], spells_remaining_to_bottom)
    hand["1 CMC"] -= Bottomable_cmc_1
    spells_remaining_to_bottom -= Bottomable_cmc_1

    # Card advantage becomes more important after a mulligan, so bottom that last
    Bottomable_draw = min(hand["Draw"], spells_remaining_to_bottom)
    hand["Draw"] -= Bottomable_draw
    spells_remaining_to_bottom -= Bottomable_draw

    # In case of unusual all land and all rock hands, bottom the remainder
    Bottomable_rock = min(hand["Rock"], spells_remaining_to_bottom)
    hand["Rock"] -= Bottomable_rock
    spells_remaining_to_bottom -= Bottomable_rock

    return hand


def put_land_on_bottom(hand: CardBag, count: int) -> CardBag:
    return hand - CardBag({"Land": count})


def do_we_keep(hand: CardBag, cards_to_keep: int, free: bool = False) -> bool:
    if cards_to_keep <= 4:
        return True
    min_lands = 3 if cards_to_keep == 7 and free else 2
    if hand["Sol Ring"] > 0:
        min_lands = 1
    max_lands = 5 if cards_to_keep > 5 else 6
    if cards_to_keep == 7:
        max_lands -= hand["Rock"]
    return min_lands <= hand["Land"] <= max_lands
