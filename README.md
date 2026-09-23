# Super X Helper

**Super X Helper** is a Linux-native hardware control, diagnostics, and quality-of-life application for the **ONEXPLAYER Super X**, developed first against Ubuntu on the liquid-cooled edition.

The practical goal is simple: make the Super X pleasant to daily-drive without reinstalling Windows or bouncing between terminal commands and unrelated utilities.

> **Status: pre-alpha.** The GTK4/libadwaita read-only application exists and has been exercised on the development Super X. Production hardware writes are still disabled until individually validated.

## Current project strategy

The project now follows a **reuse-first** rule:

1. **Daily-driver Linux control center** — continue the existing Ubuntu-native GTK app and validate ordinary Linux-supported writes.
2. **Upstream audit before new hardware-control code** — Loadout now overlaps heavily with fan curves, TDP, battery, RGB, persistence, concurrency, and safety handling. Audit/adapt proven design patterns before inventing another stack.
3. **Frost Bay** — the public BLE protocol is already substantially documented and implemented by community HHD work. Our job is local Super X validation, BlueZ transport hardening, and safe adaptation into our capability contract.
4. **Mini SSD reliability** — expose safe telemetry now, but keep reliability NOT_QUALIFIED until the separate root-cause/qualification research passes.

    trustworthy baseline
       ↓
    capability/backend contract
       ↓
    GTK daily-driver application              COMPLETE FOR READ-ONLY SHELL
       ↓
    upstream reuse audit + root write validation
       ↓
    PRE-ASTRA CHECKPOINT
       ↓
    Frost Bay local validation + Mini SSD research
       ↓
    production integration

See [ROADMAP.md](ROADMAP.md).

## Current baseline

The local Super X baseline includes:

- ONEXPLAYER SUPER X / board revision onec1;
- BIOS V1.01;
- Ubuntu 24.04.4 LTS / kernel 7.0.0-30-generic at the 2026-09-07 live pass;
- AMD RYZEN AI MAX+ 395 / Radeon 8060S;
- amd-pstate-epp, CPU boost and power telemetry;
- 2880×1800 internal display with 120 Hz support in the baseline;
- amdgpu backlight and battery telemetry;
- KIOXIA internal NVMe plus BIWIN Mini SSD at PCIe Gen4 x2;
- MediaTek Bluetooth adapter on hci0.

### Important oxpec correction

The installed 7.0.0-30-generic oxpec module **does not contain the Super X DMI quirk** and did not expose a live oxp_ec hwmon on the development machine. Upstream added Super X support later. Internal fan writes therefore remain unvalidated until a kernel/backport containing that quirk is loaded and exercised under root.

See [docs/LIVE_INTEGRATION_HANDOFF.md](docs/LIVE_INTEGRATION_HANDOFF.md).

## Architecture

    GTK4/libadwaita UI (unprivileged)
                ↓ ServiceClient
    system D-Bus + polkit
                ↓
    Python superx-helperd service facade
                ↓
      platform / storage / Frost Bay backends

Key decisions:

- keep the existing Python core for v0.1;
- GTK4/libadwaita via PyGObject for the Ubuntu-first UI;
- root-owned system D-Bus service for validated privileged writes;
- no network listener;
- no arbitrary sysfs paths/shell strings from UI input;
- Ubuntu .deb packaging first;
- user profiles as versioned high-level JSON;
- quick access as a compact second GTK window, not a new input driver.

See [docs/adr/0001-python-gtk-dbus-architecture.md](docs/adr/0001-python-gtk-dbus-architecture.md).

## Capability-driven UI

The UI consumes a stable typed contract rather than hardware paths.

Capability states:

- CONFIRMED_LOCAL
- SUPPORTED_UNVERIFIED
- READ_ONLY
- RESEARCH_PENDING
- UNAVAILABLE
- ERROR

A discovered writable node does not make can_write true.

See [docs/UI_CONTRACT.md](docs/UI_CONTRACT.md).

## Upstream reuse policy

Before implementing production fan/TDP/RGB/battery behavior, review [docs/UPSTREAM_OWNERSHIP.md](docs/UPSTREAM_OWNERSHIP.md).

In particular, [Loadout](https://github.com/srsholmes/loadout) now provides a useful reference for:

- generic hwmon fan discovery;
- PWM/RPM-target control;
- persisted fan modes/profiles;
- operation serialization and stale-tick handling;
- bounded writes to avoid wedged-EC lockups;
- independent thermal safety watchdog behavior;
- ownership restoration;
- TDP control and OneXPlayer capability detection.

That does **not** prove Super X compatibility. Loadout's published tested devices do not currently include the Super X, and our Ubuntu GTK architecture remains intentionally different.

## Frost Bay state

Frost Bay is still RESEARCH_PENDING **locally**, but not because the protocol is unknown.

Public work now documents the core FFE0/FFE1 state-and-control protocol and HHD has open Frost Bay/cooling-dock implementations. Super X Helper should reproduce that public evidence on the actual Super X and validate BlueZ reliability before enabling control.

See [docs/FROST_BAY.md](docs/FROST_BAY.md).

## Mini SSD state

    Mini SSD
    NVME_PRESENT / PCIE_ONLY / ABSENT
    Reliability: NOT_QUALIFIED

Enumeration or SMART success never silently promotes the drive to HEALTHY. No credible public root-cause/firmware breakthrough has changed that position as of 2026-09-22.

See [docs/MINI_SSD.md](docs/MINI_SSD.md).

## Read-only diagnostics

superx-diag supports:

- DMI/kernel/module state;
- hwmon/thermal/power telemetry;
- display/battery state;
- PCIe/NVMe controller + namespace discovery;
- Mini SSD presence classification;
- allow-listed SMART/error fields when nvme-cli is available;
- filtered relevant kernel messages;
- passive cached Bluetooth metadata without starting a scan;
- default redaction of SSD serials and Bluetooth addresses.

Unique identifiers require explicit opt-in.

## Safety rules

- Unknown EC registers and BLE characteristics are not fuzz targets.
- Platform writes are disabled by default until individually production-qualified.
- Requested state must be read back and match before an operation succeeds.
- A failed prerequisite aborts dependent writes.
- Internal fan control must have a tested path back to automatic/firmware ownership.
- Mini SSD reliability remains untrusted until qualification passes.
- Frost Bay disconnect/staleness/partial GATT state never counts as healthy.
- Published upstream behavior is evidence, not local authorization.

See [AGENTS.md](AGENTS.md) and [docs/RESEARCH_METHOD.md](docs/RESEARCH_METHOD.md).

## Current development handoff

The GTK4/libadwaita shell and read-only pages are built. The first live-machine integration pass refreshed the baseline and corrected the UI/service boundary; that handoff reported 45 passing tests.

The next work is:

1. audit Loadout's fan/TDP implementation before writing our production stack;
2. boot/backport an oxpec version containing the Super X quirk and validate oxp_ec under root;
3. validate EPP → boost → brightness → fan one reversible capability at a time;
4. keep Frost Bay disabled until the published protocol is reproduced locally through BlueZ.

## Non-goals for the current milestone

- rebuilding the GTK shell that already exists;
- creating another controller kernel/input stack;
- broad ONEXPLAYER support before the Super X is solid;
- blind overclocking/power-limit experimentation;
- reverse-engineering Frost Bay from scratch when public evidence already exists;
- declaring the Mini SSD healthy from one successful boot or SMART result.

## Project philosophy

**Useful software for uncommon problems.**
