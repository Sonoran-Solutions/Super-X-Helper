# Super X Helper

**Super X Helper** is a Linux-native hardware control, diagnostics, and quality-of-life application for the **ONEXPLAYER Super X**, developed first against Ubuntu on the liquid-cooled edition.

The practical goal is simple: make the Super X pleasant to daily-drive without reinstalling Windows or bouncing between terminal commands and unrelated utilities.

> **Status: pre-alpha / pre-Astra daily-driver build.** Read-only discovery is being hardened first; real hardware writes remain disabled until individually validated on the development Super X.

## Current project strategy

The project has three workstreams, but they no longer block each other:

1. **Daily-driver Linux control center** — build the OneXConsole-style UI around ordinary Linux-supported controls first.
2. **Frost Bay** — later reverse-engineer the external cooler's Bluetooth protocol and activate its already-reserved UI/backend capability.
3. **Mini SSD reliability** — expose safe telemetry now, but keep reliability `NOT_QUALIFIED` until the separate root-cause/qualification research passes.

```text
trustworthy baseline
   ↓
capability/backend contract
   ↓
GTK daily-driver application
   ↓
PRE-ASTRA CHECKPOINT
   ↓
Frost Bay + Mini SSD deep research
   ↓
activate confirmed research backends
```

## Current baseline

The original local capture established:

- ONEXPLAYER SUPER X / board revision `onec1`;
- BIOS `V1.01`;
- Ubuntu 24.04.4 LTS / kernel 7.0.0-30-generic at capture time;
- AMD RYZEN AI MAX+ 395 / Radeon 8060S;
- `amd-pstate-epp`, CPU boost and powercap telemetry;
- 2880×1800 internal display with 120 Hz support reported in the capture;
- amdgpu backlight and battery telemetry;
- KIOXIA internal NVMe plus BIWIN Mini SSD at PCIe Gen4 x2 during the baseline;
- MediaTek Bluetooth adapter on `hci0`;
- `oxpec` module and Super X DMI support present, but `oxpec` was **not loaded during the captured baseline**.

That last distinction matters: kernel support is evidence, but it is not proof that fan writes have been safely exercised on this exact device.

## Architecture

The pre-Astra architecture is now accepted:

```text
GTK4/libadwaita UI (unprivileged)
            ↓ ServiceClient
system D-Bus + polkit
            ↓
Python superx-helperd service facade
            ↓
  ┌─────────┼──────────┐
platform  storage   Frost Bay (later)
```

Key decisions:

- keep the existing Python core for v0.1;
- GTK4/libadwaita via PyGObject for the Ubuntu-first UI;
- root-owned system D-Bus service for validated privileged writes;
- no network listener;
- no arbitrary sysfs paths/shell strings from UI input;
- Ubuntu `.deb` packaging first;
- user profiles as versioned high-level JSON;
- quick access as a compact second GTK window, not a new input driver.

See [`docs/adr/0001-python-gtk-dbus-architecture.md`](docs/adr/0001-python-gtk-dbus-architecture.md).

## Capability-driven UI

The UI consumes a stable typed contract rather than hardware paths.

Capability states:

```text
CONFIRMED_LOCAL
SUPPORTED_UNVERIFIED
READ_ONLY
RESEARCH_PENDING
UNAVAILABLE
ERROR
```

A capability also reports read/write support, local validation, observed/desired value, allowed range/options, owner/backend, warnings, safety state and whether a write is actually authorized.

**Finding a writable sysfs node does not make `can_write` true.**

See [`docs/UI_CONTRACT.md`](docs/UI_CONTRACT.md).

### Frost Bay before research

```text
Frost Bay
RESEARCH_PENDING
Linux protocol/health semantics not validated
```

### Mini SSD before research

```text
Mini SSD
NVME_PRESENT / PCIE_ONLY / ABSENT
Reliability: NOT_QUALIFIED
```

Enumeration or SMART success never silently promotes the drive to `HEALTHY`.

## Read-only diagnostics

`superx-diag` is the first executable tool. The hardened collector supports:

- DMI/kernel/module state;
- hwmon/thermal/power telemetry;
- display/battery state;
- PCIe/NVMe controller + namespace discovery;
- Mini SSD presence classification;
- allow-listed SMART/error fields when `nvme-cli` is available;
- filtered relevant kernel messages;
- passive cached Frost-Bay-like BlueZ metadata without starting a scan;
- default redaction of SSD serials and Bluetooth addresses.

Unique identifiers require explicit `--include-identifiers` opt-in.

## Safety rules

- Unknown EC registers and BLE characteristics are not fuzz targets.
- Platform writes are disabled by default until individually production-qualified.
- Requested state must be read back and match before an operation succeeds.
- A failed prerequisite (for example entering manual fan mode) aborts dependent writes.
- No automatic fan rollback is claimed until it is actually implemented/tested.
- The Mini SSD is untrusted storage until qualification passes.
- Loss/staleness of future Frost Bay telemetry can never count as healthy.

See [`AGENTS.md`](AGENTS.md) and [`docs/RESEARCH_METHOD.md`](docs/RESEARCH_METHOD.md).

## Current development handoff

The GTK4/libadwaita shell and read-only pages are built, and the first live-machine integration pass has refreshed the read-only baseline and corrected the UI/service boundary. The suite is at **45 passing tests**.

The next task is live write validation under a root session (EPP → boost → brightness, then fan once `oxpec` has a Super X quirk). No hardware write is authorized yet.

See [`docs/LIVE_INTEGRATION_HANDOFF.md`](docs/LIVE_INTEGRATION_HANDOFF.md), [`docs/PHASE0_HANDOFF.md`](docs/PHASE0_HANDOFF.md) and [`ROADMAP.md`](ROADMAP.md).

## Non-goals for the pre-Astra milestone

- game-library replacement for Steam/Lutris/Heroic;
- new controller kernel driver;
- broad ONEXPLAYER support before the Super X is solid;
- blind overclocking/power-limit experimentation;
- Frost Bay control before protocol evidence exists;
- declaring the Mini SSD healthy from one successful boot or SMART result.

## Project philosophy

**Useful software for uncommon problems.**
