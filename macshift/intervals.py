"""Duration parsing and rotation-interval strategies.

Three strategies are supported:

* ``FixedInterval`` — always returns the same window.
* ``JitteredInterval`` — a fixed window plus or minus a percentage of jitter.
* ``RandomInterval`` — a fresh random window in ``[min, max]`` per rotation.

A randomized cadence is the privacy-correct default: a fixed rotation period
is itself a fingerprint a tracker can correlate.
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass

_DURATION_RE = re.compile(
    r"^\s*(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>s|sec|secs|second|seconds|"
    r"m|min|mins|minute|minutes|h|hr|hrs|hour|hours)?\s*$",
    re.IGNORECASE,
)

_UNIT_SECONDS = {
    "s": 1, "sec": 1, "secs": 1, "second": 1, "seconds": 1,
    "m": 60, "min": 60, "mins": 60, "minute": 60, "minutes": 60,
    "h": 3600, "hr": 3600, "hrs": 3600, "hour": 3600, "hours": 3600,
}


class DurationError(ValueError):
    """Raised when a duration string can't be parsed."""


def parse_duration(text: str) -> int:
    """Parse a human duration like ``45m`` or ``1h`` into integer seconds.

    A bare integer (``"90"``) is interpreted as seconds.
    """
    if text is None:
        raise DurationError("duration is required")
    match = _DURATION_RE.match(str(text))
    if not match:
        raise DurationError(f"invalid duration: {text!r}")
    value = float(match.group("value"))
    unit = (match.group("unit") or "s").lower()
    seconds = int(round(value * _UNIT_SECONDS[unit]))
    if seconds <= 0:
        raise DurationError(f"duration must be positive: {text!r}")
    return seconds


def format_duration(seconds: float) -> str:
    """Format seconds as a compact ``Hh Mm Ss`` string."""
    seconds = max(0, int(seconds))
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    parts = []
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if secs or not parts:
        parts.append(f"{secs}s")
    return " ".join(parts)


@dataclass(frozen=True)
class FixedInterval:
    seconds: int

    def __post_init__(self) -> None:
        if self.seconds <= 0:
            raise DurationError("interval must be positive")

    def next(self, rng: random.Random | None = None) -> int:
        return self.seconds

    def describe(self) -> str:
        return f"fixed {format_duration(self.seconds)}"


@dataclass(frozen=True)
class JitteredInterval:
    seconds: int
    jitter_percent: float

    def __post_init__(self) -> None:
        if self.seconds <= 0:
            raise DurationError("interval must be positive")
        if not 0 <= self.jitter_percent < 100:
            raise DurationError("jitter must be in [0, 100)")

    def next(self, rng: random.Random | None = None) -> int:
        rng = rng or random
        spread = self.seconds * (self.jitter_percent / 100.0)
        low = max(1, int(round(self.seconds - spread)))
        high = max(low, int(round(self.seconds + spread)))
        return rng.randint(low, high)

    def describe(self) -> str:
        return (
            f"jitter ±{self.jitter_percent:g}% around "
            f"{format_duration(self.seconds)}"
        )


@dataclass(frozen=True)
class RandomInterval:
    minimum: int
    maximum: int

    def __post_init__(self) -> None:
        if self.minimum <= 0 or self.maximum <= 0:
            raise DurationError("random interval bounds must be positive")
        if self.minimum > self.maximum:
            raise DurationError("random interval min must be <= max")

    def next(self, rng: random.Random | None = None) -> int:
        rng = rng or random
        return rng.randint(self.minimum, self.maximum)

    def describe(self) -> str:
        return (
            f"random {format_duration(self.minimum)}–"
            f"{format_duration(self.maximum)}"
        )


Interval = FixedInterval | JitteredInterval | RandomInterval


def build_interval(
    *,
    interval: str | None,
    random_interval: tuple[str, str] | None,
    jitter: float | None,
) -> Interval:
    """Build the appropriate interval strategy from parsed CLI arguments."""
    if random_interval is not None:
        lo = parse_duration(random_interval[0])
        hi = parse_duration(random_interval[1])
        return RandomInterval(minimum=lo, maximum=hi)
    seconds = parse_duration(interval) if interval else 3600
    if jitter:
        return JitteredInterval(seconds=seconds, jitter_percent=float(jitter))
    return FixedInterval(seconds=seconds)
