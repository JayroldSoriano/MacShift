"""Command-line entry point and subcommand wiring."""

from __future__ import annotations

import argparse
import os
import platform as platform_mod
import sys
import time

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from macshift import __author__, __repo__, __version__, mac as mac_mod, ui
from macshift.core import RotationConfig, run as run_rotation
from macshift.intervals import DurationError, build_interval
from macshift.platforms import UnsupportedPlatformError, get_platform


# ---------------------------------------------------------------------------
# argparse builder
# ---------------------------------------------------------------------------


def _add_run_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--interval",
        metavar="DURATION",
        help="Fixed rotation window (e.g. 30s, 45m, 1h). Default: 1h.",
    )
    parser.add_argument(
        "--random-interval",
        nargs=2,
        metavar=("MIN", "MAX"),
        help=(
            "Pick a fresh random window in [MIN, MAX] before every rotation. "
            "PRIVACY-RECOMMENDED MODE."
        ),
    )
    parser.add_argument(
        "--jitter",
        type=float,
        metavar="PERCENT",
        help=(
            "Apply ± PERCENT jitter to --interval "
            "(e.g. --interval 1h --jitter 25 -> windows in 45m..75m)."
        ),
    )
    parser.add_argument(
        "--interface",
        metavar="NAME",
        help="Override interface auto-detection.",
    )
    parser.add_argument(
        "--no-restore",
        action="store_true",
        help="Leave the last random MAC on exit (default restores original).",
    )
    parser.add_argument(
        "--oui",
        choices=("auto", "vendor", "random"),
        default="auto",
        help=(
            "MAC style. 'vendor' = Apple-OUI mimicry, 'random' = "
            "locally-administered, 'auto' picks per OS (default)."
        ),
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Rotate a single time, then exit.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Emit one JSON event per line and skip the live UI.",
    )
    parser.add_argument(
        "--quiet", action="store_true", help="Suppress decorative output."
    )
    parser.add_argument(
        "--verbose", action="store_true", help="Show extra diagnostic events."
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="macshift",
        description=(
            "macshift — privacy-first MAC address rotator.\n"
            f"by {__author__}  •  {__repo__}"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-V",
        "--version",
        action="store_true",
        help="Print version info and exit.",
    )

    sub = parser.add_subparsers(dest="command")

    run_p = sub.add_parser("run", help="Run the rotation loop (default).")
    _add_run_flags(run_p)

    sub.add_parser(
        "doctor",
        help="Probe whether MAC rotation works on this machine.",
    )
    sub.add_parser("list", help="Show interfaces, current MACs, link state.")
    sub.add_parser("restore", help="Restore the saved original MAC and exit.")

    # Bare flags before any subcommand should still work for the default
    # ``run`` action — attach them to the top-level parser too.
    _add_run_flags(parser)
    return parser


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _print_version(console: Console) -> None:
    text = Text("macshift ", style="bold magenta")
    text.append(f"v{__version__}\n", style="bold white")
    text.append(f"by {__author__}\n", style="white")
    text.append(__repo__, style="cyan underline")
    console.print(Panel(text, border_style="bright_magenta", expand=False))


def _require_root(console: Console) -> bool:
    if os.geteuid() == 0:
        return True
    console.print(
        "[red]Root privileges required.[/red] Re-run with:  "
        "[bold]sudo macshift[/bold]"
    )
    return False


def _check_platform(console: Console) -> bool:
    try:
        get_platform()
        return True
    except UnsupportedPlatformError as exc:
        console.print(f"[red]{exc}[/red]")
        return False


# ---------------------------------------------------------------------------
# Subcommand handlers
# ---------------------------------------------------------------------------


def cmd_run(args: argparse.Namespace) -> int:
    console = ui.make_console(quiet=args.quiet)
    if not _check_platform(console):
        return 2
    if not _require_root(console):
        return 1
    try:
        interval = build_interval(
            interval=args.interval,
            random_interval=tuple(args.random_interval)
            if args.random_interval
            else None,
            jitter=args.jitter,
        )
    except DurationError as exc:
        console.print(f"[red]Invalid interval:[/red] {exc}")
        return 2

    config = RotationConfig(
        interval=interval,
        interface=args.interface,
        oui_style=args.oui,
        no_restore=args.no_restore,
        once=args.once,
        json_output=args.json_output,
        quiet=args.quiet,
    )
    return run_rotation(config, console=console)


def cmd_list(_: argparse.Namespace) -> int:
    console = ui.make_console()
    if not _check_platform(console):
        return 2
    platform_module = get_platform()
    table = Table(title="Network interfaces", border_style="magenta")
    table.add_column("name", style="bold")
    table.add_column("kind")
    table.add_column("mac", style="cyan")
    table.add_column("link")
    for info in platform_module.list_interfaces():
        link = (
            Text("up", style="bold green")
            if info.link_up
            else Text("down", style="bold red")
        )
        table.add_row(info.name, info.kind, info.mac, link)
    console.print(table)
    return 0


def cmd_restore(_: argparse.Namespace) -> int:
    """``restore`` reapplies the OS-assigned MAC.

    macshift does not persist the original MAC across runs (a stored MAC could
    itself become a tracking vector). The most reliable way to recover the OEM
    MAC is to power-cycle the interface so the OS reassigns it. We do exactly
    that and report what the OS settled on.
    """
    console = ui.make_console()
    if not _check_platform(console):
        return 2
    if not _require_root(console):
        return 1
    platform_module = get_platform()
    iface = platform_module.active_interface()
    before = platform_module.current_mac(iface)
    system = platform_mod.system()

    if system == "Darwin":
        import subprocess

        subprocess.run(
            ["networksetup", "-setairportpower", iface, "off"],
            capture_output=True,
        )
        time.sleep(1)
        subprocess.run(
            ["networksetup", "-setairportpower", iface, "on"],
            capture_output=True,
        )
    else:
        import subprocess

        subprocess.run(
            ["ip", "link", "set", "dev", iface, "down"], capture_output=True
        )
        subprocess.run(
            ["ip", "link", "set", "dev", iface, "up"], capture_output=True
        )

    # Give the OS a moment to reassign and re-associate.
    time.sleep(3)
    after = platform_module.current_mac(iface)
    console.print(
        f"interface [bold]{iface}[/bold]: [cyan]{before}[/cyan] "
        f"-> [bold cyan]{after}[/bold cyan]"
    )
    return 0


def cmd_doctor(_: argparse.Namespace) -> int:
    console = ui.make_console()
    ui.banner(console)

    system = platform_mod.system()
    machine = platform_mod.machine()
    apple_silicon = system == "Darwin" and machine.startswith(("arm", "aarch"))

    findings: list[tuple[str, bool, str]] = []
    findings.append(
        ("operating system", system in ("Linux", "Darwin"), f"{system} {machine}")
    )

    if system not in ("Linux", "Darwin"):
        _render_findings(console, findings)
        console.print("[red]✗ macshift does not support this OS yet.[/red]")
        return 2

    platform_module = get_platform()
    tools = platform_module.available_tools()
    for name, present in tools.items():
        findings.append((f"tool: {name}", present, "found" if present else "missing"))

    # Interfaces
    try:
        interfaces = platform_module.list_interfaces()
        findings.append(
            ("interfaces", bool(interfaces), f"{len(interfaces)} found")
        )
    except Exception as exc:
        findings.append(("interfaces", False, str(exc)))
        interfaces = []

    # Active interface
    active = None
    try:
        active = platform_module.active_interface()
        findings.append(("active interface", True, active))
    except Exception as exc:
        findings.append(("active interface", False, str(exc)))

    if apple_silicon:
        findings.append(
            (
                "Apple Silicon Wi-Fi",
                False,
                "the OS frequently rejects MAC changes on built-in Wi-Fi",
            )
        )

    # Real spoof-then-restore test (requires root)
    spoof_ok = False
    spoof_msg = "skipped — re-run with sudo to test"
    if active and os.geteuid() == 0:
        spoof_ok, spoof_msg = _probe_spoof(platform_module, active)
    findings.append(("spoof + revert test", spoof_ok, spoof_msg))

    _render_findings(console, findings)

    critical_pass = all(
        ok for label, ok, _ in findings if label != "Apple Silicon Wi-Fi"
    )
    verdict = (
        Text("PASS — rotation should work on this machine.", style="bold green")
        if critical_pass and spoof_ok
        else Text(
            "FAIL — see findings above; rotation likely will not work as-is.",
            style="bold red",
        )
    )
    console.print(Panel(verdict, border_style="magenta", expand=False))
    return 0 if critical_pass and spoof_ok else 1


def _probe_spoof(platform_module, iface: str) -> tuple[bool, str]:
    """Apply a test MAC, verify it stuck, then restore the original."""
    original = platform_module.current_mac(iface)
    style = "vendor" if platform_mod.system() == "Darwin" else "random"
    candidate = mac_mod.generate(style).address
    try:
        platform_module.set_mac(iface, candidate)
    except Exception as exc:
        return False, f"set_mac raised: {exc}"
    now = platform_module.current_mac(iface)
    stuck = now.lower() == candidate.lower()
    # Best-effort restore.
    try:
        platform_module.set_mac(iface, original)
    except Exception as exc:
        return stuck, f"applied {candidate}; restore failed: {exc}"
    return stuck, (
        f"applied {candidate}, restored {original}"
        if stuck
        else f"set_mac returned ok but MAC stayed at {now}"
    )


def _render_findings(
    console: Console, findings: list[tuple[str, bool, str]]
) -> None:
    table = Table(title="doctor findings", border_style="magenta")
    table.add_column("check", style="bold")
    table.add_column("status")
    table.add_column("detail")
    for label, ok, detail in findings:
        status = (
            Text("✓", style="bold green") if ok else Text("✗", style="bold red")
        )
        table.add_row(label, status, detail)
    console.print(table)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    console = ui.make_console()

    if args.version:
        _print_version(console)
        return 0

    command = args.command or "run"
    if command == "run":
        return cmd_run(args)
    if command == "doctor":
        return cmd_doctor(args)
    if command == "list":
        return cmd_list(args)
    if command == "restore":
        return cmd_restore(args)
    parser.error(f"unknown command: {command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
