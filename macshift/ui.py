"""Terminal UI: startup banner, live dashboard, session summary, JSON events."""

from __future__ import annotations

import json
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

from rich.align import Align
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from macshift import __author__, __repo__, __version__


_BRAND = "macshift"
_PRIMARY = "bold cyan"
_DIM = "dim"


def make_console(*, quiet: bool = False) -> Console:
    # ``emoji=False`` is critical: MAC fragments like ``:ab:`` would otherwise
    # render as 🆎 because Rich treats ``:name:`` as an emoji shortcode.
    return Console(quiet=quiet, highlight=False, emoji=False)


def banner(console: Console) -> None:
    title = Text(_BRAND, style="bold magenta")
    title.append(f"  v{__version__}", style="bold white")
    subtitle = Text("privacy-first MAC address rotator", style="italic cyan")
    author = Text(f"by {__author__}", style="white")
    link = Text(_repo_short(), style="cyan underline")

    body = Group(
        Align.center(title),
        Align.center(subtitle),
        Align.center(Text("")),
        Align.center(author),
        Align.center(link),
    )
    console.print(
        Panel(
            body,
            border_style="bright_magenta",
            padding=(1, 4),
            expand=False,
        )
    )


def _repo_short() -> str:
    return __repo__.replace("https://", "")


# ---------------------------------------------------------------------------
# Dashboard state
# ---------------------------------------------------------------------------


@dataclass
class DashboardState:
    interface: str = "?"
    network: str = "?"
    current_mac: str = "?"
    mac_label: str = ""
    mode: str = "?"
    connection: str = "starting"  # connected | reconnecting | down | starting
    connected_at: float | None = None
    window_seconds: int = 0
    rotations: int = 0
    started_at: float = field(default_factory=time.time)
    last_event: str = ""

    def uptime_on_mac(self) -> int:
        if self.connected_at is None:
            return 0
        return max(0, int(time.time() - self.connected_at))

    def remaining(self) -> int:
        if self.connected_at is None:
            return self.window_seconds
        return max(0, int(self.connected_at + self.window_seconds - time.time()))


# ---------------------------------------------------------------------------
# Dashboard rendering
# ---------------------------------------------------------------------------


def _conn_badge(status: str) -> Text:
    palette = {
        "connected": ("● connected", "bold green"),
        "reconnecting": ("● reconnecting", "bold yellow"),
        "down": ("● link down", "bold red"),
        "starting": ("● starting", "bold blue"),
    }
    text, style = palette.get(status, ("● unknown", "white"))
    return Text(text, style=style)


def _format_secs(seconds: int) -> str:
    seconds = max(0, int(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h {m:02d}m {s:02d}s"
    return f"{m}m {s:02d}s"


def render_dashboard(state: DashboardState) -> Panel:
    table = Table.grid(padding=(0, 2))
    table.add_column(style=_DIM, justify="right", no_wrap=True)
    table.add_column(style="white")

    table.add_row("interface", state.interface)
    table.add_row("network", state.network)

    mac_text = Text(state.current_mac, style=_PRIMARY)
    if state.mac_label:
        mac_text.append(f"  ({state.mac_label})", style=_DIM)
    table.add_row("current MAC", mac_text)

    table.add_row("mode", state.mode)
    table.add_row("status", _conn_badge(state.connection))
    table.add_row("uptime on MAC", _format_secs(state.uptime_on_mac()))
    table.add_row("next rotation", _format_secs(state.remaining()))
    table.add_row("rotations", str(state.rotations))

    runtime = int(time.time() - state.started_at)
    table.add_row("session runtime", _format_secs(runtime))

    last = Text(state.last_event or "—", style=_DIM)

    body = Group(table, Text(""), last)

    title = Text(f"{_BRAND} ", style="bold magenta")
    title.append(f"v{__version__}", style="dim white")

    return Panel(
        body,
        title=title,
        border_style="bright_magenta",
        padding=(1, 2),
        expand=False,
    )


class LiveDashboard:
    """Thin wrapper around ``rich.live.Live`` used by the rotation core."""

    def __init__(self, console: Console, state: DashboardState) -> None:
        self.console = console
        self.state = state
        self._live: Live | None = None

    def __enter__(self) -> "LiveDashboard":
        self._live = Live(
            render_dashboard(self.state),
            console=self.console,
            refresh_per_second=4,
            transient=False,
        )
        self._live.__enter__()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._live is not None:
            self._live.__exit__(exc_type, exc, tb)
            self._live = None

    def refresh(self) -> None:
        if self._live is not None:
            self._live.update(render_dashboard(self.state))


# ---------------------------------------------------------------------------
# JSON event emitter
# ---------------------------------------------------------------------------


def emit_json(event: str, **fields: Any) -> None:
    payload = {
        "ts": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "event": event,
        **fields,
    }
    sys.stdout.write(json.dumps(payload) + "\n")
    sys.stdout.flush()


# ---------------------------------------------------------------------------
# Session summary
# ---------------------------------------------------------------------------


def print_summary(
    console: Console,
    *,
    rotations: int,
    runtime_seconds: int,
    restored_to: str | None,
    final_mac: str | None,
) -> None:
    table = Table.grid(padding=(0, 2))
    table.add_column(style=_DIM, justify="right")
    table.add_column(style="white")
    table.add_row("rotations", str(rotations))
    table.add_row("runtime", _format_secs(runtime_seconds))
    if restored_to:
        table.add_row("restored MAC", Text(restored_to, style="bold green"))
    elif final_mac:
        table.add_row("final MAC", Text(final_mac, style="bold yellow"))
    console.print(
        Panel(
            table,
            title=Text("session summary", style="bold magenta"),
            border_style="magenta",
            padding=(1, 2),
            expand=False,
        )
    )


def state_snapshot(state: DashboardState) -> dict[str, Any]:
    snap = asdict(state)
    snap.pop("started_at", None)
    snap["uptime_on_mac"] = state.uptime_on_mac()
    snap["remaining"] = state.remaining()
    return snap
