"""Tests for duration parsing and interval strategies."""

from __future__ import annotations

import random

import pytest

from macshift.intervals import (
    DurationError,
    FixedInterval,
    JitteredInterval,
    RandomInterval,
    build_interval,
    format_duration,
    parse_duration,
)


@pytest.mark.parametrize(
    "text,expected",
    [
        ("30s", 30),
        ("30", 30),
        ("45m", 45 * 60),
        ("1h", 3600),
        ("2hr", 7200),
        ("90 seconds", 90),
        ("1.5h", 5400),
        ("  10m  ", 600),
    ],
)
def test_parse_duration_valid(text: str, expected: int):
    assert parse_duration(text) == expected


@pytest.mark.parametrize("text", ["", "0", "0s", "-5m", "abc", "5x", None])
def test_parse_duration_invalid(text):
    with pytest.raises(DurationError):
        parse_duration(text)


def test_format_duration_compact():
    assert format_duration(0) == "0s"
    assert format_duration(45) == "45s"
    assert format_duration(60) == "1m"
    assert format_duration(125) == "2m 5s"
    assert format_duration(3600) == "1h"
    assert format_duration(3725) == "1h 2m 5s"


def test_fixed_interval_always_same():
    interval = FixedInterval(seconds=600)
    assert all(interval.next() == 600 for _ in range(20))
    assert "fixed" in interval.describe()


def test_fixed_interval_rejects_nonpositive():
    with pytest.raises(DurationError):
        FixedInterval(seconds=0)
    with pytest.raises(DurationError):
        FixedInterval(seconds=-1)


def test_jittered_interval_stays_within_bounds():
    interval = JitteredInterval(seconds=3600, jitter_percent=25)
    rng = random.Random(0)
    for _ in range(500):
        value = interval.next(rng)
        assert 2700 <= value <= 4500
    assert "±25%" in interval.describe()


def test_jittered_interval_rejects_bad_percent():
    with pytest.raises(DurationError):
        JitteredInterval(seconds=60, jitter_percent=-1)
    with pytest.raises(DurationError):
        JitteredInterval(seconds=60, jitter_percent=100)


def test_random_interval_stays_within_bounds():
    interval = RandomInterval(minimum=20 * 60, maximum=90 * 60)
    rng = random.Random(0)
    for _ in range(500):
        value = interval.next(rng)
        assert 20 * 60 <= value <= 90 * 60


def test_random_interval_rejects_inverted_bounds():
    with pytest.raises(DurationError):
        RandomInterval(minimum=100, maximum=50)


def test_random_interval_describe_mentions_both_bounds():
    desc = RandomInterval(minimum=600, maximum=1800).describe()
    assert "10m" in desc
    assert "30m" in desc


def test_build_interval_prefers_random_when_provided():
    interval = build_interval(
        interval="1h", random_interval=("20m", "90m"), jitter=None
    )
    assert isinstance(interval, RandomInterval)
    assert interval.minimum == 20 * 60
    assert interval.maximum == 90 * 60


def test_build_interval_applies_jitter():
    interval = build_interval(interval="1h", random_interval=None, jitter=25)
    assert isinstance(interval, JitteredInterval)
    assert interval.seconds == 3600
    assert interval.jitter_percent == 25


def test_build_interval_defaults_to_fixed_one_hour():
    interval = build_interval(interval=None, random_interval=None, jitter=None)
    assert isinstance(interval, FixedInterval)
    assert interval.seconds == 3600
