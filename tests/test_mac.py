"""Tests for MAC generation and validation."""

from __future__ import annotations

import random

import pytest

from macshift.mac import (
    APPLE_OUIS,
    generate,
    is_locally_administered,
    is_unicast,
    is_valid_mac,
    matches_apple_oui,
)


def test_is_valid_mac_accepts_well_formed():
    assert is_valid_mac("aa:bb:cc:dd:ee:ff")
    assert is_valid_mac("00:00:00:00:00:00")
    assert is_valid_mac("AA:BB:CC:DD:EE:FF")


@pytest.mark.parametrize(
    "bad",
    [
        "",
        "aa:bb:cc:dd:ee",
        "aa-bb-cc-dd-ee-ff",
        "ZZ:bb:cc:dd:ee:ff",
        "aabbccddeeff",
        "aa:bb:cc:dd:ee:ff:00",
    ],
)
def test_is_valid_mac_rejects_malformed(bad: str):
    assert not is_valid_mac(bad)


@pytest.mark.parametrize("seed", list(range(50)))
def test_random_style_is_locally_administered_unicast(seed: int):
    rng = random.Random(seed)
    mac = generate("random", rng=rng)
    assert is_valid_mac(mac.address)
    assert is_locally_administered(mac.address)
    assert is_unicast(mac.address)
    assert mac.label == "locally-administered"


@pytest.mark.parametrize("seed", list(range(50)))
def test_vendor_style_uses_apple_oui(seed: int):
    rng = random.Random(seed)
    mac = generate("vendor", rng=rng)
    assert is_valid_mac(mac.address)
    assert matches_apple_oui(mac.address)
    assert mac.label.startswith("Apple OUI ")
    assert mac.address.lower()[:8] in APPLE_OUIS


def test_random_macs_differ_across_calls():
    rng = random.Random(0)
    seen = {generate("random", rng=rng).address for _ in range(20)}
    assert len(seen) >= 19  # collisions astronomically unlikely


def test_generate_unknown_style_raises():
    with pytest.raises(ValueError):
        generate("nope")


def test_apple_ouis_are_well_formed():
    for oui in APPLE_OUIS:
        assert len(oui) == 8
        parts = oui.split(":")
        assert len(parts) == 3
        for part in parts:
            assert len(part) == 2
            int(part, 16)  # raises if not hex
