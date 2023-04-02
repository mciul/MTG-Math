import logging
import random
from collections import defaultdict
from dataclasses import dataclass, replace
from itertools import product
from typing import Dict, Generator, List, Tuple

logger = logging.getLogger()


CardBag = Dict[str, int]
CurveTuple = Tuple[int, int, int, int, int, int, int, int]


def nearby_values(start_value: int) -> Generator[int, None, None]:
    for value in range(max(start_value - 1, 0), start_value + 2):
        yield value


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
    def start(cls, curve: Curve) -> "GameState":
        library = []
        for card, count in curve.decklist.items():
            library += [card] * count
        random.shuffle(library)
        hand: CardBag = defaultdict(int)
        for _ in range(7):
            card = library.pop(0)
            hand[card] += 1
        return cls(library, hand)
