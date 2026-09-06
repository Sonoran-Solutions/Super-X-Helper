# Super X Helper

**Super X Helper** is a Linux-first hardware control, diagnostics, and quality-of-life project for the **ONEXPLAYER Super X**, developed primarily against Ubuntu on the liquid-cooled Super X configuration.

The immediate goal is selfish and practical: make the hardware features paid for on the Super X usable without reinstalling Windows.

Longer term, the project may become a clean Linux control center for the device and a useful reference for other ONEXPLAYER Linux users.

> **Status: research / pre-alpha.** Do not trust experimental hardware-control code with unattended operation, important data, or maximum-power profiles yet.

## Why this project exists

The Super X runs very well under Linux, but several pieces of the Windows experience still depend on ONEXPLAYER's proprietary OneXConsole software or have unresolved platform behavior.

The project currently focuses on three workstreams:

1. **Linux control center** — provide one place for performance, fan, battery, display, and related device controls that currently require separate Linux tools or terminal commands.
2. **Frost Bay support** — reverse-engineer and implement safe Linux control/telemetry for the external Frost Bay liquid cooler, whose software communication is handled over Bluetooth.
3. **Mini SSD reliability** — determine why the removable 2 TB Mini SSD can intermittently disappear or become unreliable, establish whether the root cause is software, firmware, power management, signal/contact quality, thermals, or hardware, and document a reproducible fix or mitigation.

## Current technical baseline

Useful pieces already exist upstream and should be reused rather than reimplemented:

- The Linux `oxpec` platform driver includes an `ONEXPLAYER SUPER X` DMI match and exposes ONEXPLAYER platform controls such as fan/PWM and related EC-backed features.
- Linux users have already demonstrated Super X fan control through the `oxpec`/hwmon interface.
- CPU/package power configuration can be implemented through existing Linux interfaces/tools such as RyzenAdj where an upstream kernel interface is not available.
- ONEXPLAYER documents Frost Bay software control as Bluetooth-based; the liquid-cooling tubes themselves do not carry control data.
- The BIWIN CL100 Mini SSD is a PCIe Gen4 x2 / NVMe 1.4 device, so standard Linux PCIe/NVMe diagnostics can be used to isolate where disappearance occurs.

These facts make Super X Helper primarily an **integration + reverse-engineering project**, not a replacement kernel or emulator project.

## Product vision

The eventual user experience should be a small native control center backed by a privileged hardware service rather than a GUI that shells out arbitrary commands.

```text
┌────────────────────── Super X Helper ──────────────────────┐
│                                                            │
│ PERFORMANCE                                                 │
│   Profile        Balanced                                  │
│   Power target   45 W                                      │
│   CPU boost      On                                        │
│                                                            │
│ COOLING                                                     │
│   Internal fans  Auto                                      │
│   Frost Bay      Connected                                 │
│   Pump           72%                                       │
│   Radiator fan   Auto                                      │
│   Flow / health  Normal                                    │
│                                                            │
│ POWER / DEVICE                                              │
│   Charge limit   80%                                       │
│   Display        2880×1800 @ 120 Hz                         │
│   RGB / controls available where supported                 │
│                                                            │
│ STORAGE                                                     │
│   Mini SSD       Connected · Healthy · 52 °C                │
│   Reliability    No link resets detected                   │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

Per-game profiles may eventually allow the system to apply an appropriate power/cooling configuration automatically when a game launches.

## Architecture direction

```text
                         Super X Helper UI
                                │
                         unprivileged IPC
                                │
                    superx-helper daemon/service
                                │
        ┌───────────────────────┼─────────────────────────┐
        │                       │                         │
   Platform backend       Frost Bay backend        Storage monitor
        │                       │                         │
 oxpec / hwmon / sysfs      BlueZ / BLE             PCIe / NVMe
 RyzenAdj where needed      protocol layer           kernel telemetry
 power/display APIs         safety state             diagnostics
```

The UI must not directly write EC registers, raw BLE characteristics, or arbitrary sysfs paths.

See [`DESIGN.md`](DESIGN.md) for the proposed architecture and [`ROADMAP.md`](ROADMAP.md) for the phased task list.

## Research tracks

### Frost Bay

The first objective is **protocol discovery**, not a pretty UI.

Research should establish:

- Bluetooth identity and discovery behavior;
- advertised services and GATT characteristics;
- read/notify/write semantics;
- safe commands and telemetry fields;
- connection/failure behavior;
- whether a health/flow state participates in enabling the Super X's liquid-cooled power envelope.

See [`docs/FROST_BAY.md`](docs/FROST_BAY.md).

### Mini SSD

The first objective is **fault isolation**.

The project should distinguish at least:

```text
A. PCIe endpoint disappears entirely
B. PCIe endpoint remains but NVMe controller/block device disappears
C. NVMe remains but I/O/filesystem fails
D. device remains functional but thermals/performance become unsafe
```

No important data should be stored on the test Mini SSD until the failure mode is reproduced and reliability is established.

See [`docs/MINI_SSD.md`](docs/MINI_SSD.md).

### Linux platform controls

The control-center work should inventory existing upstream interfaces before implementing anything custom. Prefer kernel/sysfs/DBus APIs and maintained projects over direct EC writes.

See [`docs/LINUX_INTEGRATION.md`](docs/LINUX_INTEGRATION.md).

## Development principles

1. **Evidence before hardware writes.** Unknown EC registers or BLE characteristics are not experimentation targets by default.
2. **One variable per experiment.** Especially for power-management and Mini SSD debugging.
3. **Fail safe.** Loss of Frost Bay communication must never silently leave an unsafe high-power policy enabled.
4. **Reuse upstream Linux support.** Do not fork functionality that is already available and maintained upstream.
5. **Separate research from production code.** Confirmed protocol/interface facts should be documented before the GUI depends on them.
6. **Do not trust the Mini SSD yet.** Test data only until long-duration reliability is demonstrated.
7. **Keep the project Ubuntu-friendly first.** Broader distro support can follow after the Super X itself works reliably.

## Repository layout

```text
.
├── README.md
├── DESIGN.md
├── ROADMAP.md
├── AGENTS.md
└── docs/
    ├── FROST_BAY.md
    ├── MINI_SSD.md
    ├── LINUX_INTEGRATION.md
    └── RESEARCH_METHOD.md
```

Implementation directories will be added only after the relevant architecture and language choices are validated.

## Initial success criteria

The first meaningful release should be able to claim all of the following:

- normal Linux Super X controls are available from one interface without proprietary Windows software;
- Frost Bay can be discovered, monitored, and safely controlled from Linux;
- Mini SSD behavior is instrumented well enough to distinguish connection, controller, I/O, thermal, and power-management failures;
- any Mini SSD mitigation shipped by the project is backed by repeatable tests rather than anecdotal kernel flags;
- no experimental feature requires blind EC writes or stores important user data on unvalidated storage.

## Non-goals for the first version

- Reimplementing Steam, Lutris, Heroic, or another game launcher.
- Replacing the Linux kernel's ONEXPLAYER drivers.
- Supporting every ONEXPLAYER model before the Super X is solid.
- Automatically overclocking or bypassing thermal/power protections.
- Treating a single successful Mini SSD boot as proof of reliability.
- Reverse engineering unrelated OneXConsole cloud/account services.

## Hardware under development

Primary target:

- ONEXPLAYER Super X, liquid-cooled edition
- Frost Bay external liquid cooler
- BIWIN Mini SSD, 2 TB
- Ubuntu Linux

Other configurations are welcome later, but behavior must not be assumed identical without evidence.

## Project philosophy

**Useful software for uncommon problems.**

The goal is not to recreate OneXConsole pixel-for-pixel. It is to provide a Linux-native experience that makes the Super X's hardware dependable, observable, and pleasant to use.