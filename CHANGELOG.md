# Changelog

All notable changes to **macshift** are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-06-19

### Added
- Initial public release.
- Cross-platform Python core for Linux and macOS, packaged as a real Python
  distribution (`pipx install .`) with `macshift` console entry point and
  `python -m macshift` support.
- Three interval strategies for rotation cadence:
  - `--interval` — fixed window.
  - `--random-interval MIN MAX` — fresh random window each rotation
    (privacy-recommended).
  - `--jitter PERCENT` — ± jitter around a fixed window.
- `run` subcommand with a live `rich`-powered dashboard: interface, network,
  current MAC + provenance, mode, connection status badge, uptime on MAC,
  rotation countdown, total rotations, session runtime.
- `doctor` subcommand that probes OS, architecture (flags Apple Silicon),
  required CLI tools, interfaces, and runs a real spoof-then-restore test on
  the active interface.
- `list` subcommand showing a table of interfaces, MACs, and link state.
- `restore` subcommand that power-cycles the interface so the OS reassigns
  the OEM MAC.
- `--json` mode that bypasses the UI and emits one structured event per line
  for automation pipelines.
- `--once` and `--no-restore` flags for one-shot operation and stealth exits.
- Locally-administered unicast MAC generation on Linux, Apple-OUI mimicry on
  macOS (real Apple OUIs are reused; macOS frequently rejects LA addresses).
- Clean signal handling: `SIGINT` / `SIGTERM` stop the loop, restore the
  original MAC, and print a session summary.

[1.0.0]: https://github.com/JayroldSoriano/MacShift/releases/tag/v1.0.0
