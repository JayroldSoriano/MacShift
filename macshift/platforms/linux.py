"""Linux platform adapter."""

from __future__ import annotations

import re
import shutil
import subprocess

from macshift.platforms import InterfaceInfo


def _run(cmd: list[str], check: bool = True) -> str:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if check and result.returncode != 0:
        raise RuntimeError(
            f"Command failed: {' '.join(cmd)}\n{result.stderr.strip()}"
        )
    return result.stdout.strip()


def active_interface() -> str:
    out = _run(["ip", "route", "show", "default"])
    match = re.search(r"dev\s+(\S+)", out)
    if not match:
        raise RuntimeError(
            "Couldn't find an active default route. Are you online?"
        )
    return match.group(1)


def current_mac(iface: str) -> str:
    out = _run(["ip", "link", "show", iface])
    match = re.search(r"link/ether\s+([0-9a-fA-F:]{17})", out)
    return match.group(1) if match else "unknown"


def is_connected(iface: str) -> bool:
    try:
        with open(f"/sys/class/net/{iface}/operstate") as fh:
            if fh.read().strip() != "up":
                return False
    except FileNotFoundError:
        return False
    out = _run(["ip", "route", "show", "default"], check=False)
    return f"dev {iface}" in out


def network_name(iface: str) -> str:
    try:
        if shutil.which("iwgetid"):
            ssid = _run(["iwgetid", "-r"], check=False)
            if ssid:
                return ssid
        if shutil.which("nmcli"):
            out = _run(
                ["nmcli", "-t", "-f", "active,ssid", "dev", "wifi"],
                check=False,
            )
            for line in out.splitlines():
                if line.startswith("yes:"):
                    return line.split(":", 1)[1]
    except Exception:
        pass
    return "wired-or-unknown"


def set_mac(iface: str, mac: str) -> None:
    _run(["ip", "link", "set", "dev", iface, "down"])
    _run(["ip", "link", "set", "dev", iface, "address", mac])
    _run(["ip", "link", "set", "dev", iface, "up"])
    if shutil.which("nmcli"):
        subprocess.run(
            ["nmcli", "device", "connect", iface], capture_output=True
        )


def list_interfaces() -> list[InterfaceInfo]:
    out = _run(["ip", "-o", "link", "show"], check=False)
    infos: list[InterfaceInfo] = []
    for line in out.splitlines():
        match = re.match(
            r"\d+:\s+(?P<name>\S+?):\s+<(?P<flags>[^>]*)>.*"
            r"link/ether\s+(?P<mac>[0-9a-fA-F:]{17})",
            line,
        )
        if not match:
            continue
        name = match.group("name").split("@", 1)[0]
        if name == "lo":
            continue
        kind = "wifi" if name.startswith(("wl", "wlan", "wlp")) else "ethernet"
        infos.append(
            InterfaceInfo(
                name=name,
                kind=kind,
                mac=match.group("mac"),
                link_up="UP" in match.group("flags"),
            )
        )
    return infos


def available_tools() -> dict[str, bool]:
    return {
        tool: shutil.which(tool) is not None
        for tool in ("ip", "nmcli", "iw", "iwgetid")
    }
