from __future__ import annotations

import math
import random

from simulator.config import GaussianDistribution, UniformIntDistribution


class Distributions:
    """
    Stateless sampler functions backed by a seeded random.Random instance.

    All public methods return Python int or float — no numpy dependency in Phase 1.
    Negative samples from Gaussian distributions are clamped to a minimum of 1
    so token counts and latencies are always positive.
    """

    def __init__(self, rng: random.Random) -> None:
        self._rng = rng

    @classmethod
    def from_seed(cls, seed: int | None) -> "Distributions":
        rng = random.Random(seed)
        return cls(rng)

    def gaussian_int(self, dist: GaussianDistribution, minimum: int = 1) -> int:
        """Sample a Gaussian, round to nearest int, clamp to minimum."""
        raw = self._rng.gauss(dist.mean, dist.std)
        return max(minimum, math.floor(raw + 0.5))

    def gaussian_ms(self, dist: GaussianDistribution, minimum_ms: float = 0.0) -> float:
        """Sample a Gaussian latency in milliseconds, clamped to minimum_ms."""
        raw = self._rng.gauss(dist.mean, dist.std)
        return max(minimum_ms, raw)

    def uniform_int(self, dist: UniformIntDistribution) -> int:
        """Sample a uniform integer in [min, max] inclusive."""
        return self._rng.randint(dist.min, dist.max)

    def choice(self, items: list[str]) -> str:
        """Pick one item uniformly at random from a list."""
        return self._rng.choice(items)

    def bernoulli(self, probability: float) -> bool:
        """Return True with the given probability."""
        return self._rng.random() < probability

    def randint(self, a: int, b: int) -> int:
        """Return a random integer N such that a <= N <= b."""
        return self._rng.randint(a, b)
