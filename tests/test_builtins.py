import math
import pytest
from src.scripting.builtins import (
    clamp, square, triangle, sawtooth,
)


def test_clamp():
    assert clamp(5, 0, 10) == 5
    assert clamp(-1, 0, 10) == 0
    assert clamp(15, 0, 10) == 10


def test_square():
    assert square(0, 10) == 1
    assert square(4.9, 10) == 1
    assert square(5.1, 10) == 0
    assert square(9.9, 10) == 0


def test_triangle():
    assert triangle(0, 10) == 0.0
    assert triangle(5, 10) == 1.0
    assert triangle(10, 10) == 0.0


def test_sawtooth():
    assert sawtooth(0, 10) == 0.0
    assert sawtooth(5, 10) == 0.5
    assert sawtooth(9.99, 10) == pytest.approx(0.999, abs=0.01)
