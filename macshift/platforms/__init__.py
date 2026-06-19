"""Per-OS platform adapters.

Each adapter exposes the same interface, used by :mod:`macshift.core`:

* ``active_interface()``                       -> str
* ``list_interfaces()``                        -> list[InterfaceInfo]
* ``current_mac(iface: str)``                  -> str
* ``set_mac(iface: str, mac: str)``            -> None
* ``is_connected(iface: str)``                 -> bool
* ``network_name(iface: str)``                 -> str
* ``available_tools()``                        -> dict[str, bool]
"""

from __future__ import annotations

import platform
from dataclasses import dataclass


@dataclass(frozen=True)
class InterfaceInfo:
    name: str
    kind: str  # "wifi" | "ethernet" | "other"
    mac: str
    link_up: bool


def get_platform():
    """Return the platform adapter module for the current OS."""
    system = platform.system()
    if system == "Linux":
        from macshift.platforms import linux

        return linux
    if system == "Darwin":
        from macshift.platforms import macos

        return macos
    raise UnsupportedPlatformError(system)


class UnsupportedPlatformError(RuntimeError):
    """Raised when macshift is started on an unsupported OS."""

    def __init__(self, system: str) -> None:
        super().__init__(
            f"{system} is not supported yet. macshift currently supports "
            "Linux and macOS. PRs welcome at "
            "https://github.com/JayroldSoriano/MacShift"
        )
        self.system = system
