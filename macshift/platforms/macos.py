"""macOS platform adapter.

The MAC can only be set on Wi-Fi while the interface is NOT associated with an
AP. We power-cycle the radio, then race a tight retry loop of
``ifconfig <iface> ether <mac>`` in the brief window before the OS re-associates.

On recent macOS — especially Apple Silicon built-in Wi-Fi — the OS frequently
blocks the change regardless. Run ``macshift doctor`` to know in advance.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import time

from macshift.platforms import InterfaceInfo


def _run(cmd: list[str], check: bool = True) -> str:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if check and result.returncode != 0:
        raise RuntimeError(
            f"Command failed: {' '.join(cmd)}\n{result.stderr.strip()}"
        )
    return result.stdout.strip()


def active_interface() -> str:
    out = _run(["route", "-n", "get", "default"])
    match = re.search(r"interface:\s+(\S+)", out)
    if not match:
        raise RuntimeError(
            "Couldn't find an active default route. Are you online?"
        )
    return match.group(1)


def current_mac(iface: str) -> str:
    out = _run(["ifconfig", iface])
    match = re.search(r"ether\s+([0-9a-fA-F:]{17})", out)
    return match.group(1) if match else "unknown"


def is_connected(iface: str) -> bool:
    try:
        out = _run(["ifconfig", iface], check=False)
        return "status: active" in out
    except Exception:
        return False


def network_name(iface: str) -> str:
    try:
        # Recent macOS redacts the SSID from this command for privacy; an empty
        # result here is cosmetic and expected.
        out = _run(["networksetup", "-getairportnetwork", iface], check=False)
        match = re.search(r"Network:\s+(.+)$", out)
        if match:
            return match.group(1).strip()
    except Exception:
        pass
    return "wired-or-unknown"


def _wifi_device() -> str | None:
    """Return the device name of the first Wi-Fi hardware port, if any."""
    try:
        out = _run(["networksetup", "-listallhardwareports"], check=False)
    except Exception:
        return None
    blocks = out.split("\n\n")
    for block in blocks:
        if "Wi-Fi" in block or "AirPort" in block:
            match = re.search(r"Device:\s+(\S+)", block)
            if match:
                return match.group(1)
    return None


def set_mac(iface: str, mac: str) -> None:
    wifi_dev = _wifi_device()
    is_wifi = wifi_dev == iface

    if is_wifi:
        subprocess.run(
            ["networksetup", "-setairportpower", iface, "off"],
            capture_output=True,
        )
        time.sleep(1)
        subprocess.run(
            ["networksetup", "-setairportpower", iface, "on"],
            capture_output=True,
        )

    deadline = time.time() + 4
    last_err = "unknown error"
    while time.time() < deadline:
        result = subprocess.run(
            ["ifconfig", iface, "ether", mac],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return
        last_err = result.stderr.strip() or last_err
        time.sleep(0.3)
    raise RuntimeError(last_err)


def list_interfaces() -> list[InterfaceInfo]:
    wifi_dev = _wifi_device()
    try:
        out = _run(["ifconfig", "-l"], check=False)
    except Exception:
        return []
    names = [n for n in out.split() if n and n != "lo0"]
    infos: list[InterfaceInfo] = []
    for name in names:
        try:
            block = _run(["ifconfig", name], check=False)
        except Exception:
            continue
        mac_match = re.search(r"ether\s+([0-9a-fA-F:]{17})", block)
        if not mac_match:
            continue
        kind = "wifi" if name == wifi_dev else "ethernet"
        link_up = "status: active" in block
        infos.append(
            InterfaceInfo(
                name=name,
                kind=kind,
                mac=mac_match.group(1),
                link_up=link_up,
            )
        )
    return infos


def available_tools() -> dict[str, bool]:
    return {
        tool: shutil.which(tool) is not None
        for tool in ("ifconfig", "networksetup", "route")
    }
