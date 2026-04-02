"""
behavior/sampler.py
Samples a value for any attribute type declared in the profile schema.
Supported types: float, int, enum, boolean
All sampling goes through here — no other module generates attribute values directly.
"""
from __future__ import annotations

import random
from typing import Any

from simulator.config import AttributeConfig, AttributeType


class AttributeSampler:
    """Generates a correctly typed value for any AttributeConfig."""

    def sample(self, attr_cfg: AttributeConfig, rng: random.Random) -> Any:
        if attr_cfg.type == AttributeType.FLOAT:
            return self._sample_float(attr_cfg, rng)
        if attr_cfg.type == AttributeType.INT:
            return self._sample_int(attr_cfg, rng)
        if attr_cfg.type == AttributeType.ENUM:
            return self._sample_enum(attr_cfg, rng)
        if attr_cfg.type == AttributeType.BOOLEAN:
            return self._sample_boolean(attr_cfg, rng)
        raise ValueError(f"Unknown attribute type: {attr_cfg.type}")

    def _sample_float(self, cfg: AttributeConfig, rng: random.Random) -> float:
        # Gaussian when mean is declared, uniform when only min/max are given.
        if cfg.mean is not None:
            std = cfg.std if cfg.std is not None else cfg.mean * 0.1
            value = rng.gauss(cfg.mean, std)
        else:
            lo = cfg.min if cfg.min is not None else 0.0
            hi = cfg.max if cfg.max is not None else lo + 1.0
            value = rng.uniform(lo, hi)
        lo = cfg.min if cfg.min is not None else float("-inf")
        hi = cfg.max if cfg.max is not None else float("inf")
        return float(max(lo, min(hi, value)))

    def _sample_int(self, cfg: AttributeConfig, rng: random.Random) -> int:
        # Fixed value list takes priority over min/max range.
        if cfg.values is not None:
            return int(rng.choice(cfg.values))
        lo = int(cfg.min) if cfg.min is not None else 0
        hi = int(cfg.max) if cfg.max is not None else lo
        return rng.randint(lo, hi)

    def _sample_enum(self, cfg: AttributeConfig, rng: random.Random) -> str:
        return str(rng.choice(cfg.values))

    def _sample_boolean(self, cfg: AttributeConfig, rng: random.Random) -> bool:
        prob = cfg.probability if cfg.probability is not None else 0.5
        return rng.random() < prob
