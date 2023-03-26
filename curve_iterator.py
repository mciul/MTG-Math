#!/usr/bin/env python

from typing import Generator, Tuple

from itertools import product


def bracket(best_value: int) -> Generator[int, None, None]:
    for value in range(max(best_value - 1, 0), best_value + 2):
        yield value


def curves(
    best_one: int,
    best_two: int,
    best_three: int,
    best_four: int,
    best_five: int,
    best_six: int,
    rock: int,
) -> Generator[Tuple[int, int, int, int, int, int, int], None, None]:
    ranges = [
        bracket(best_value)
        for best_value in [
            best_one,
            best_two,
            best_three,
            best_four,
            best_five,
            best_six,
            rock,
        ]
    ]
    return product(*ranges)


for one, two, three, four, five, six, rock in curves(2, 3, 4, 4, 5, 4, 2):
    print(f"{one=} {two=} {three=} {four=} {five=} {six=} {rock=}")
