"""Rotation lifecycle: snapshot original MAC, rotate, wait, repeat."""

from __future__ import annotations

import signal
import time
from dataclasses import dataclass
from typing import Callable

from rich.console import Console

from macshift import mac as mac_mod
from macshift import ui
from macshift.intervals import Interval
from macshift.platforms import UnsupportedPlatformError, get_platform


@dataclass
class RotationConfig:
    interval: Interval
    interface: str | None = None
    oui_style: str = "auto"  # "auto" | "vendor" | "random"
    no_restore: bool = False
    once: bool = False
    json_output: bool = False
    quiet: bool = False
    reconnect_timeout: int = 60


def _resolve_style(config: RotationConfig, system: str) -> str:
    if config.oui_style == "auto":
        return "vendor" if system == "Darwin" else "random"
    return config.oui_style


def _signal_handler_factory(stop_flag: dict) -> Callable[[int, object], None]:
    def handler(signum, frame):  # noqa: ARG001
        stop_flag["stop"] = True

    return handler


def run(config: RotationConfig, console: Console | None = None) -> int:
    """Run the rotation loop until interrupted or ``--once`` finishes."""
    import platform as platform_mod

    console = console or ui.make_console(quiet=config.quiet)
    system = platform_mod.system()

    try:
        platform_module = get_platform()
    except UnsupportedPlatformError as exc:
        console.print(f"[red]{exc}[/red]")
        return 2

    iface = config.interface or platform_module.active_interface()
    style = _resolve_style(config, system)
    original_mac = platform_module.current_mac(iface)
    network = platform_module.network_name(iface)

    if not config.json_output:
        ui.banner(console)

    state = ui.DashboardState(
        interface=iface,
        network=network,
        current_mac=original_mac,
        mac_label="original",
        mode=config.interval.describe(),
        connection="starting",
    )

    stop_flag = {"stop": False}
    handler = _signal_handler_factory(stop_flag)
    signal.signal(signal.SIGINT, handler)
    signal.signal(signal.SIGTERM, handler)

    rotations = 0
    started_at = time.time()
    final_mac = original_mac
    restored_to: str | None = None

    if config.json_output:
        ui.emit_json(
            "start",
            interface=iface,
            network=network,
            original_mac=original_mac,
            mode=config.interval.describe(),
        )
        rotations, final_mac = _rotation_loop_json(
            config=config,
            platform_module=platform_module,
            iface=iface,
            style=style,
            stop_flag=stop_flag,
        )
    else:
        with ui.LiveDashboard(console, state) as dash:
            rotations, final_mac = _rotation_loop_live(
                config=config,
                platform_module=platform_module,
                iface=iface,
                style=style,
                stop_flag=stop_flag,
                dash=dash,
            )

    if not config.no_restore:
        try:
            platform_module.set_mac(iface, original_mac)
            restored_to = original_mac
            final_mac = original_mac
            if config.json_output:
                ui.emit_json("restored", mac=original_mac)
        except Exception as exc:
            if config.json_output:
                ui.emit_json("restore_failed", error=str(exc))
            else:
                console.print(f"[yellow]Could not restore MAC: {exc}[/yellow]")
                if system == "Darwin":
                    console.print(
                        "[dim]On macOS, toggling Wi-Fi off/on lets the OS "
                        "reassign its own address if needed.[/dim]"
                    )

    if config.json_output:
        ui.emit_json(
            "stop",
            rotations=rotations,
            runtime_seconds=int(time.time() - started_at),
            final_mac=final_mac,
        )
    else:
        ui.print_summary(
            console,
            rotations=rotations,
            runtime_seconds=int(time.time() - started_at),
            restored_to=restored_to,
            final_mac=final_mac,
        )
    return 0


def _rotate_once(
    *,
    platform_module,
    iface: str,
    style: str,
) -> mac_mod.GeneratedMac:
    new = mac_mod.generate(style)
    platform_module.set_mac(iface, new.address)
    return new


def _interruptible_sleep(seconds: int, stop_flag: dict, *, tick: float = 0.5) -> None:
    deadline = time.time() + seconds
    while time.time() < deadline and not stop_flag["stop"]:
        time.sleep(min(tick, max(0.0, deadline - time.time())))


def _wait_for_connection(
    platform_module, iface: str, timeout: int, stop_flag: dict
) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline and not stop_flag["stop"]:
        if platform_module.is_connected(iface):
            return True
        time.sleep(2)
    return False


def _rotation_loop_live(
    *,
    config: RotationConfig,
    platform_module,
    iface: str,
    style: str,
    stop_flag: dict,
    dash: ui.LiveDashboard,
) -> tuple[int, str]:
    rotations = 0
    last_mac = dash.state.current_mac

    while not stop_flag["stop"]:
        window = config.interval.next()
        dash.state.window_seconds = window
        dash.state.connection = "reconnecting"
        dash.state.last_event = "applying fresh MAC…"
        dash.refresh()

        try:
            new = _rotate_once(
                platform_module=platform_module, iface=iface, style=style
            )
        except Exception as exc:
            dash.state.last_event = f"set_mac failed: {exc}"
            dash.state.connection = "down"
            dash.refresh()
            break

        last_mac = new.address
        dash.state.current_mac = new.address
        dash.state.mac_label = new.label
        dash.state.connected_at = time.time()
        dash.state.last_event = "waiting for reconnect…"
        dash.refresh()

        connected = _wait_for_connection(
            platform_module, iface, config.reconnect_timeout, stop_flag
        )
        if stop_flag["stop"]:
            break
        dash.state.connection = "connected" if connected else "down"
        dash.state.connected_at = time.time()
        dash.state.last_event = (
            "reconnected" if connected else "no link within timeout"
        )
        rotations += 1
        dash.state.rotations = rotations
        dash.refresh()

        if config.once:
            break

        # Hold this MAC for the rotation window.
        end = time.time() + window
        while time.time() < end and not stop_flag["stop"]:
            dash.refresh()
            if not platform_module.is_connected(iface):
                dash.state.connection = "down"
            else:
                dash.state.connection = "connected"
            _interruptible_sleep(min(1, max(0, int(end - time.time()))), stop_flag)

    return rotations, last_mac


def _rotation_loop_json(
    *,
    config: RotationConfig,
    platform_module,
    iface: str,
    style: str,
    stop_flag: dict,
) -> tuple[int, str]:
    rotations = 0
    last_mac = platform_module.current_mac(iface)

    while not stop_flag["stop"]:
        window = config.interval.next()
        ui.emit_json("rotating", planned_window_seconds=window)
        try:
            new = _rotate_once(
                platform_module=platform_module, iface=iface, style=style
            )
        except Exception as exc:
            ui.emit_json("rotation_failed", error=str(exc))
            break
        last_mac = new.address
        ui.emit_json("rotated", mac=new.address, label=new.label)

        connected = _wait_for_connection(
            platform_module, iface, config.reconnect_timeout, stop_flag
        )
        ui.emit_json("connection", connected=connected)
        rotations += 1

        if config.once:
            break

        _interruptible_sleep(window, stop_flag)

    return rotations, last_mac
