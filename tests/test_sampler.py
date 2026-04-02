"""
tests/test_sampler.py
Verifies AttributeSampler generates correctly typed values within declared bounds.
"""
from __future__ import annotations

import random

import pytest

from simulator.behavior.sampler import AttributeSampler
from simulator.config import AttributeConfig, AttributeType


@pytest.fixture
def rng() -> random.Random:
    return random.Random(42)


@pytest.fixture
def sampler() -> AttributeSampler:
    return AttributeSampler()


# ---------------------------------------------------------------------------
# float type
# ---------------------------------------------------------------------------

def test_float_uniform_within_bounds(sampler, rng):
    cfg = AttributeConfig(type=AttributeType.FLOAT, min=0.6, max=1.0)
    for _ in range(500):
        val = sampler.sample(cfg, rng)
        assert isinstance(val, float)
        assert 0.6 <= val <= 1.0


def test_float_gaussian_clamped_to_min_max(sampler, rng):
    # With a tight range and wide std, values must still be clamped.
    cfg = AttributeConfig(type=AttributeType.FLOAT, mean=0.5, std=10.0, min=0.0, max=1.0)
    for _ in range(500):
        val = sampler.sample(cfg, rng)
        assert 0.0 <= val <= 1.0


def test_float_no_bounds_does_not_crash(sampler, rng):
    # When min/max are absent for a gaussian, no clamping is applied.
    cfg = AttributeConfig(type=AttributeType.FLOAT, mean=100.0, std=10.0)
    val = sampler.sample(cfg, rng)
    assert isinstance(val, float)


# ---------------------------------------------------------------------------
# int type
# ---------------------------------------------------------------------------

def test_int_range_within_bounds(sampler, rng):
    cfg = AttributeConfig(type=AttributeType.INT, min=1, max=20)
    for _ in range(500):
        val = sampler.sample(cfg, rng)
        assert isinstance(val, int)
        assert 1 <= val <= 20


def test_int_values_list_picks_from_list(sampler, rng):
    cfg = AttributeConfig(type=AttributeType.INT, values=[0, 1, 2])
    results = {sampler.sample(cfg, rng) for _ in range(200)}
    assert results <= {0, 1, 2}


def test_int_values_list_returns_all_options(sampler, rng):
    cfg = AttributeConfig(type=AttributeType.INT, values=[0, 1, 2])
    results = {sampler.sample(cfg, rng) for _ in range(300)}
    assert results == {0, 1, 2}


# ---------------------------------------------------------------------------
# enum type
# ---------------------------------------------------------------------------

def test_enum_returns_string(sampler, rng):
    cfg = AttributeConfig(type=AttributeType.ENUM, values=["cohere-v3", "bge-reranker"])
    for _ in range(100):
        val = sampler.sample(cfg, rng)
        assert isinstance(val, str)
        assert val in {"cohere-v3", "bge-reranker"}


def test_enum_covers_all_values(sampler, rng):
    cfg = AttributeConfig(type=AttributeType.ENUM, values=["a", "b", "c"])
    results = {sampler.sample(cfg, rng) for _ in range(300)}
    assert results == {"a", "b", "c"}


# ---------------------------------------------------------------------------
# boolean type
# ---------------------------------------------------------------------------

def test_boolean_returns_bool(sampler, rng):
    cfg = AttributeConfig(type=AttributeType.BOOLEAN, probability=0.5)
    for _ in range(100):
        val = sampler.sample(cfg, rng)
        assert isinstance(val, bool)


def test_boolean_high_probability_mostly_true(sampler, rng):
    cfg = AttributeConfig(type=AttributeType.BOOLEAN, probability=0.95)
    results = [sampler.sample(cfg, rng) for _ in range(1000)]
    true_rate = sum(results) / len(results)
    assert true_rate > 0.85, f"Expected >85% True, got {true_rate:.2%}"


def test_boolean_low_probability_mostly_false(sampler, rng):
    cfg = AttributeConfig(type=AttributeType.BOOLEAN, probability=0.05)
    results = [sampler.sample(cfg, rng) for _ in range(1000)]
    false_rate = sum(not r for r in results) / len(results)
    assert false_rate > 0.85, f"Expected >85% False, got {false_rate:.2%}"


def test_boolean_default_probability_near_half(sampler, rng):
    cfg = AttributeConfig(type=AttributeType.BOOLEAN)  # no probability — defaults to 0.5
    results = [sampler.sample(cfg, rng) for _ in range(1000)]
    true_rate = sum(results) / len(results)
    assert 0.40 <= true_rate <= 0.60, f"Expected ~50%, got {true_rate:.2%}"
