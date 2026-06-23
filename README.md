# macshift

> Privacy-first MAC address rotator for Linux and macOS — with randomized
> intervals, a live terminal dashboard, and a `doctor` mode that tells you up
> front whether your machine can actually rotate.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
![Python](https://img.shields.io/badge/python-3.9%2B-blue)
![Platforms](https://img.shields.io/badge/platforms-Linux%20%7C%20macOS-lightgrey)

The MAC-changer space is crowded, but the popular tools are either stale
(`SpoofMAC`), single-shot shell scripts (`macchanger`, `wipri`), or both.
**macshift** is built around two ideas the others miss:

1. **A constant rotation cadence is itself a fingerprint.** Rotating exactly
   every hour is correlatable; rotating every *21m, 47m, 33m, 81m…* is not.
   macshift makes randomized intervals a first-class feature, not a hack.
2. **Tell the user the truth before they trust the tool.** On recent macOS —
   especially Apple Silicon — the OS will silently refuse to honor a MAC
   change. `macshift doctor` performs a real spoof-then-restore probe on your
   machine and gives you a binary PASS/FAIL verdict.

---

## Install

```bash
pipx install .
# or
pip install --user .
```

Then verify:

```bash
macshift --version
macshift doctor       # run this first — it tells you if rotation will work
```

`pipx` is recommended so that the CLI lands on your `$PATH` in its own venv.
You can also run the package directly without installing the entry point:

```bash
python -m macshift --help
```

## Run script (zero-setup)

If you just want to get going without installing anything globally, use the
included `run.sh` bootstrap script:

```bash
chmod +x run.sh   # first time only
./run.sh           # prints help
```

The script will automatically:

1. Check that Python 3 is available.
2. Create a virtual environment in `.venv/` (if one doesn't already exist).
3. Install macshift and its dependencies into the venv.
4. Re-execute with `sudo` when a privileged command (`run`, `restore`) is used.

```bash
./run.sh doctor                          # probe your hardware
./run.sh list                            # show interfaces & MACs
./run.sh run                             # rotate every hour (prompts for sudo)
./run.sh run --once                      # single rotation then exit
./run.sh run --random-interval 20m 90m   # privacy-recommended mode
./run.sh restore                         # restore original MAC
```

> **Tip:** You can pass *any* macshift flags directly to `run.sh` — they are
> forwarded as-is.

## Quickstart

Rotate the active interface's MAC every hour (default):

```bash
sudo macshift run
```

**Privacy-recommended mode** — pick a fresh random window in `[20m, 90m]`
before every rotation:

```bash
sudo macshift run --random-interval 20m 90m
```

Fixed cadence with ±25% jitter (each window randomly within 45m–75m):

```bash
sudo macshift run --interval 1h --jitter 25
```

Single rotation then exit:

```bash
sudo macshift run --once
```

Machine-readable output for automation / logging pipelines:

```bash
sudo macshift run --random-interval 30m 90m --json
```

Restore the OEM MAC right now:

```bash
sudo macshift restore
```

## How it works

* **Interface discovery** — the active interface is whatever owns the default
  route (`ip route show default` on Linux, `route -n get default` on macOS).
* **MAC generation** — on Linux, macshift uses a locally-administered, unicast
  MAC (the IEEE-blessed range for software-assigned addresses). On macOS,
  it uses a real Apple OUI, because the OS frequently rejects
  locally-administered addresses on Wi-Fi.
* **Applying the MAC** — on Linux, `ip link down → set address → up`, then
  `nmcli device connect`. On macOS, the MAC can only be set while the radio is
  *not* associated, so macshift power-cycles Wi-Fi (`networksetup
  -setairportpower off/on`) and races a tight retry loop of `ifconfig <iface>
  ether <mac>` to win the brief pre-association window.
* **Rotation lifecycle** — apply MAC → wait for reconnect → hold the MAC for
  the chosen window → repeat. On `SIGINT` / `SIGTERM`, the original MAC is
  restored and a session summary is printed.

## Platform support

| Platform                          | Status                                                                                  |
|-----------------------------------|------------------------------------------------------------------------------------------|
| Linux (Wi-Fi or Ethernet)         | **Full support.** Requires `ip` and ideally `nmcli`.                                     |
| macOS Intel, Wi-Fi                | **Works**, with the usual macOS caveats around the pre-association window.               |
| macOS Apple Silicon, built-in Wi-Fi | **Frequently blocked by the OS.** Run `macshift doctor` first — it will tell you.       |
| macOS, external USB Wi-Fi adapter | Often works even on Apple Silicon. Use `macshift list` to find the device name.          |
| Windows                           | **Not yet supported.** PRs welcome.                                                      |

> **Always start with `macshift doctor`.** It probes the OS, tool availability,
> interfaces, and runs an actual spoof-then-restore test on your hardware
> before you commit to a long rotation run.

## Comparison

|                                   | macshift | `macchanger` | `SpoofMAC`   | `wipri`     |
|-----------------------------------|:--------:|:------------:|:------------:|:-----------:|
| Cross-platform (Linux + macOS)    |    ✅    |     ❌       |     ⚠️*      |     ❌      |
| Real Python package, `pipx`       |    ✅    |     ❌       |     ⚠️       |     ❌      |
| Randomized / jittered intervals   |    ✅    |     ❌       |     ❌       |     ✅      |
| Live terminal dashboard           |    ✅    |     ❌       |     ❌       |     ❌      |
| `doctor` / hardware probe         |    ✅    |     ❌       |     ❌       |     ❌      |
| Maintained for current macOS      |    ✅    |     ⚠️       |     ❌       |     ❌      |
| JSON event mode for automation    |    ✅    |     ❌       |     ❌       |     ❌      |

<sub>* SpoofMAC supports macOS but its last release (2018) predates many of the
restrictions enforced by modern macOS.</sub>

## Responsible use

macshift is privacy / anti-tracking / authorized security-testing tooling. By
using it, you agree that you will:

* Comply with all applicable laws in your jurisdiction.
* Comply with the acceptable-use terms of any network you connect to.
* **Not** use it to defeat access controls, identity checks, captive portals,
  paid-time-limit enforcement, or any other restriction you are not authorized
  to bypass.

Changing your MAC address can break network access, violate your ISP or
employer's terms of service, and is illegal in some contexts. You are
responsible for your own use of this tool.

## Author

**Jayrold Christian Soriano** — https://github.com/JayroldSoriano

Repository: https://github.com/JayroldSoriano/MacShift

## License

Released under the [MIT License](LICENSE).
