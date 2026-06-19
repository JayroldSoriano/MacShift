"""MAC address generation and validation.

Two generation styles are supported:

* **Locally-administered unicast** (Linux): bit 1 of the first octet is set and
  bit 0 is cleared. This is the IEEE-blessed range for software-assigned MACs
  and avoids collisions with real hardware.
* **Apple vendor-style** (macOS): the first three octets come from a known
  Apple OUI. macOS frequently rejects locally-administered addresses on Wi-Fi,
  so mimicking a real Apple device is more reliable.
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass

_MAC_RE = re.compile(r"^[0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5}$")

# Genuine Apple OUIs. Source: IEEE OUI registry.
APPLE_OUIS: tuple[str, ...] = (
    "a4:83:e7",
    "f0:18:98",
    "ac:bc:32",
    "88:66:5a",
    "3c:07:54",
    "8c:85:90",
    "00:25:00",
    "00:1c:b3",
    "f4:0f:24",
    "60:33:4b",
)


@dataclass(frozen=True)
class GeneratedMac:
    """A generated MAC plus a short label describing its provenance."""

    address: str
    label: str


def is_valid_mac(mac: str) -> bool:
    """Return True if *mac* is a colon-separated 6-octet MAC address."""
    return bool(_MAC_RE.match(mac))


def is_locally_administered(mac: str) -> bool:
    """Return True if the locally-administered bit (bit 1) is set."""
    if not is_valid_mac(mac):
        return False
    return bool(int(mac.split(":", 1)[0], 16) & 0x02)


def is_unicast(mac: str) -> bool:
    """Return True if the multicast bit (bit 0) is cleared."""
    if not is_valid_mac(mac):
        return False
    return not (int(mac.split(":", 1)[0], 16) & 0x01)


def matches_apple_oui(mac: str) -> bool:
    """Return True if the first three octets are a known Apple OUI."""
    if not is_valid_mac(mac):
        return False
    return mac.lower()[:8] in APPLE_OUIS


def _random_la_unicast_mac(rng: random.Random) -> str:
    first = (rng.randint(0, 255) & 0xFC) | 0x02
    octets = [first] + [rng.randint(0, 255) for _ in range(5)]
    return ":".join(f"{o:02x}" for o in octets)


def _random_apple_mac(rng: random.Random) -> tuple[str, str]:
    oui = rng.choice(APPLE_OUIS)
    tail = ":".join(f"{rng.randint(0, 255):02x}" for _ in range(3))
    return f"{oui}:{tail}", f"Apple OUI {oui}"


def generate(
    style: str = "random",
    *,
    rng: random.Random | None = None,
) -> GeneratedMac:
    """Generate a MAC according to *style*.

    Args:
        style: ``"random"`` for locally-administered unicast,
               ``"vendor"`` for Apple-OUI mimicry.
        rng:   Optional ``random.Random`` for deterministic tests.
    """
    rng = rng or random
    if style == "vendor":
        address, label = _random_apple_mac(rng)
        return GeneratedMac(address=address, label=label)
    if style == "random":
        return GeneratedMac(
            address=_random_la_unicast_mac(rng),
            label="locally-administered",
        )
    raise ValueError(f"Unknown MAC style: {style!r}")
