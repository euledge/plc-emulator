import math
import random


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(x, hi))


def square(t: float, period: float) -> float:
    return 1.0 if (t % period) < (period / 2) else 0.0


def triangle(t: float, period: float) -> float:
    phase = (t % period) / period
    return 2.0 * phase if phase < 0.5 else 2.0 * (1.0 - phase)


def sawtooth(t: float, period: float) -> float:
    return (t % period) / period


BUILTIN_FUNCTIONS = {
    "sin": math.sin,
    "cos": math.cos,
    "abs": abs,
    "min": min,
    "max": max,
    "floor": math.floor,
    "ceil": math.ceil,
    "int": int,
    "clamp": clamp,
    "random": random.random,
    "randint": random.randint,
    "square": square,
    "triangle": triangle,
    "sawtooth": sawtooth,
}
