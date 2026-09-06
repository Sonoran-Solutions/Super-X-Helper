# Super X Helper

**Super X Helper** is a Linux-first hardware control, diagnostics, and quality-of-life project for the **ONEXPLAYER Super X**, developed primarily against Ubuntu on the liquid-cooled Super X configuration.

The immediate goal is selfish and practical: **replace the parts of OneXConsole that matter for daily use without reinstalling Windows.**

Longer term, the project may become a clean Linux control center for the device and a useful reference for other ONEXPLAYER Linux users.

> **Status: pre-alpha / active integration.** The current foundation includes local hardware inventory, capability discovery, diagnostics scaffolding, and provisional platform-control code. Hardware write paths must not be considered production-validated merely because they exist or pass mocked tests.

## Current development target

Before spending premium research-model time on the two difficult unknowns, Super X Helper should become a usable Linux-native OneXConsole-style control center for everything already available through known Linux interfaces.

```text
trustworthy baseline + diagnostics
        ↓
ordinary Linux platform controls
        ↓
polished daily-driver UI + profiles + quick access
        ↓
PRE-ASTRA CHECKPOINT
        ↓
Frost Bay research + Mini SSD fault isolation
        ↓
integrate confirmed discoveries
```

See [`docs/PRE_ASTRA_CHECKPOINT.md`](docs/PRE_ASTRA_CHECKPOINT.md) for the product milestone and [`ROADMAP.md`](ROADMAP.md) for the implementation order.

## Why this project exists

The Super X runs very well under Linux, but several pieces of the Windows experience still depend on ONEXPLAYER's proprietary OneXConsole software or have unresolved platform behavior.

The project has three workstreams:

1. **Linux control center** — one place for performance, fan, battery, display, profiles, telemetry, diagnostics, and related device controls that otherwise require separate Linux tools or terminal commands.
2. **Frost Bay support** — reverse-engineer and implement safe Linux control/telemetry for the external Frost Bay liquid cooler, whose software communication is handled over Bluetooth.
3. **Mini SSD reliability** — determine why the removable 2 TB Mini SSD can intermittently disappear or become unreliable, establish whether the root cause is software, firmware, power management, signal/contact quality, thermals, or hardware, and document a reproducible fix or mitigation.

The first workstream should be largely complete **before** the other two receive deep-research-model budget.

## Current technical baseline

Useful pieces already exist upstream and should be reused rather than reimplemented:

- The running Ubuntu system includes the Linux `oxpec` platform module for ONEXPLAYER devices; local Super X DMI/kernel details are captured in [`docs/local-hardware-baseline.md`](docs/local-hardware-baseline.md).
- CPU scaling/boost, thermals, battery telemetry, display/backlight, PCIe/NVMe, and Bluetooth all expose standard Linux interfaces that can be normalized behind the application.
- The Mini SSD is visible as a BIWIN NVMe/PCIe device when present, giving Linux useful instrumentation for later fault isolation.
- Frost Bay remains a separate Bluetooth protocol research target; no local protocol implementation should be guessed into production code before direct evidence exists.

The current Gemini-generated platform/control scaffolding is useful but **provisional**. A bounded Tier-2 audit is required before write-capable UI features are enabled.

## Product vision

The daily-driver experience should be a small native control center backed by a narrow privileged service rather than a GUI that shells out arbitrary commands.

```text
┌────────────────────── Super X Helper ──────────────────────┐
│                                                            │
│ PERFORMANCE                                                 │
│   Profile        Balanced                                  │
│   Power target   45 W            (when validated)          │
│   CPU boost      On                                        │
│                                                            │
│ COOLING                                                     │
│   Internal fans  Auto                                      │
│   Frost Bay      Research pending                          │
│                                                            │
│ POWER / DISPLAY                                             │
│   Battery        99%                                       │
│   Display        2880×1800 @ 120 Hz                        │
│                                                            │
│ STORAGE                                                     │
│   Mini SSD       Present · 45 °C · PCIe Gen4 x2           │
│   Reliability    NOT QUALIFIED                             │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

After Frost Bay research, the existing cooling card/backend should activate from newly confirmed capabilities rather than require a UI redesign.

## Capability model

The UI must distinguish support state from wishful thinking.

Recommended states:

- **AVAILABLE_READ_WRITE** — locally validated telemetry and control;
- **READ_ONLY** — trustworthy telemetry but no production-qualified control;
- **SUPPORTED_UNVERIFIED** — source/interface evidence exists but this exact local control path has not passed the production gate;
- **RESEARCH_PENDING** — requires a dedicated evidence/reverse-engineering task;
- **UNAVAILABLE** — current Linux stack does not expose it;
- **ERROR** — capability is expected but currently failing.

A capability being discoverable never automatically authorizes a hardware write.

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
 power/display APIs         protocol layer           kernel telemetry
```

The UI must not directly write EC registers, raw BLE characteristics, arbitrary sysfs paths, or storage devices.

See [`DESIGN.md`](DESIGN.md) for the proposed architecture.

## Pre-Astra daily-driver scope

The target before Frost Bay/Mini SSD deep research is:

- trustworthy read-only diagnostics and capability discovery;
- CPU/performance controls where locally validated;
- internal fan telemetry/control and safe fan curves once `oxpec` behavior is confirmed on hardware;
- display brightness/resolution/refresh and VRR where the active Linux stack exposes a reliable interface;
- battery telemetry and charge/bypass features only where Linux support is proven;
- declarative Quiet/Balanced/Performance/Custom profiles;
- a compact quick-access panel for common in-game changes;
- controller/vibration/gyro integration through maintained Linux owners rather than a competing input stack;
- RGB integration if a maintained or reasonably understood Linux path exists;
- Mini SSD basic presence/link/temperature/diagnostic state with **NOT_QUALIFIED** reliability;
- a first-class Frost Bay card/status that remains **RESEARCH_PENDING** until its protocol is actually understood.

A game library is intentionally lower priority than hardware control; Steam/Heroic/Lutris already solve that problem better. Per-game **profile association** may be added without turning Super X Helper into another launcher.

## Research tracks

### Frost Bay

The product UI/backend contract should exist first. Deep research then establishes:

- Bluetooth identity and discovery behavior;
- advertised services and GATT characteristics;
- read/notify/write semantics;
- telemetry fields and freshness/health state;
- safe commands and ranges;
- connection/failure behavior;
- whether cooler health participates in enabling the liquid-cooled power envelope.

See [`docs/FROST_BAY.md`](docs/FROST_BAY.md).

### Mini SSD

Basic telemetry belongs in the daily-driver app; **reliability qualification does not** happen by assumption.

The deep-research task must distinguish at least:

```text
A. PCIe endpoint disappears entirely
B. PCIe endpoint remains but NVMe controller/namespace disappears
C. NVMe remains but I/O/filesystem fails
D. device remains functional but thermals/performance become unsafe
```

No important data should be stored on the test Mini SSD until the failure mode is reproduced and reliability is established.

See [`docs/MINI_SSD.md`](docs/MINI_SSD.md).

## Development principles

1. **Daily-driver value before exotic research.** Finish known Linux integrations before spending premium research-model budget.
2. **Evidence before hardware writes.** Unknown EC registers or BLE characteristics are not experimentation targets by default.
3. **One variable per experiment.** Especially for power-management and Mini SSD debugging.
4. **Fail safe.** Loss of Frost Bay communication must never silently leave an unsafe liquid-only high-power policy enabled.
5. **Reuse upstream Linux support.** Do not fork functionality that is already available and maintained upstream.
6. **Capability state is explicit.** Unsupported, unverified, read-only and research-pending are distinct states.
7. **Separate research from production code.** Confirmed protocol/interface facts should be documented before production controls depend on them.
8. **Do not trust the Mini SSD yet.** Test data only until long-duration reliability is demonstrated.
9. **Keep the project Ubuntu-friendly first.** Broader distro support can follow after the Super X itself works reliably.

## Model strategy

Use the Sonoran model ladder:

- **Tier 1 — Gemini 3.8 Flash / DeepSeek V4 Flash:** inventories, UI/components, tests, docs, mechanical implementation.
- **Tier 2 — GPT-5.6 Terra Medium:** serious engineering, backend/system integration, review of Tier-1 output.
- **Tier 3 — DeepSeek V4 Pro High:** difficult debugging, static reverse engineering, hard second opinions.
- **Tier 4 — GPT-6 Astra Medium/High:** undocumented protocols and experimental cross-layer research.

> **Astra should usually receive evidence produced by cheaper models rather than being asked to gather all of the evidence itself.**

For this repo, Astra should primarily be reserved for Frost Bay protocol semantics and Mini SSD fault isolation. Once an unknown is resolved, normal implementation returns to Terra/Flash.

## Repository layout

```text
.
├── README.md
├── DESIGN.md
├── ROADMAP.md
├── WALKTHROUGH.md
├── AGENTS.md
├── src/
├── tests/
└── docs/
    ├── PRE_ASTRA_CHECKPOINT.md
    ├── FROST_BAY.md
    ├── MINI_SSD.md
    ├── LINUX_INTEGRATION.md
    ├── UPSTREAM_OWNERSHIP.md
    ├── local-hardware-baseline.md
    └── RESEARCH_METHOD.md
```

## Success criteria

### Pre-Astra checkpoint

- the normal application is pleasant enough to use instead of separate terminal commands for routine Super X management;
- confirmed platform controls work from one UI;
- profiles and quick access work;
- Mini SSD basic telemetry is visible but reliability is not overstated;
- Frost Bay is visible as `RESEARCH_PENDING` without guessed protocol code.

### Later first meaningful research-integrated release

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