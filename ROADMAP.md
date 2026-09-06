# Super X Helper — Roadmap and Task List

This roadmap is intentionally research-first. The project should not spend weeks building UI around interfaces that have not yet been proven on the actual Super X.

Priority meanings:

- **P0** — required before any meaningful implementation work.
- **P1** — core project capability.
- **P2** — quality-of-life / hardening.
- **RESEARCH** — evidence-gathering task whose result may change later implementation.

Model guidance:

- **Astra High** — use for ambiguous reverse engineering, cross-layer root-cause work, and architecture decisions where experiments must be designed autonomously.
- **Terra Medium** — use for ordinary implementation once interfaces/protocols are known.
- **Luna** — use for mechanical docs/tests/cleanup.

---

# Phase 0 — Establish a trustworthy hardware baseline

## SX-001 · Capture immutable hardware/software inventory — P0 / RESEARCH

Record:

- exact Super X SKU / liquid-cooled edition identity;
- DMI vendor/product/board strings;
- BIOS/UEFI version;
- Ubuntu release;
- kernel version;
- CPU/GPU identity;
- Bluetooth adapter and driver;
- internal SSD identity;
- Mini SSD PCIe/NVMe identity when detected;
- Frost Bay advertised Bluetooth identity when powered;
- currently loaded ONEXPLAYER/platform modules.

**Acceptance:** `docs/local-hardware-baseline.md` contains enough information to distinguish this test machine from another Super X revision without exposing secrets.

**Recommended model:** Terra Medium.

## SX-002 · Inventory existing Linux controls — P0 / RESEARCH

Identify every useful control already exposed by current Linux interfaces:

- `oxpec`/hwmon fan controls and telemetry;
- turbo/performance toggles where available;
- battery charge controls;
- RyzenAdj or kernel power-limit controls;
- display resolution/refresh/VRR interfaces;
- RGB support through existing maintained projects;
- controller/gyro/device support through HHD/InputPlumber or alternatives.

Classify each capability as:

- upstream and stable;
- available through maintained userspace tooling;
- available only through workaround;
- missing.

**Acceptance:** implementation plan does not duplicate a maintained upstream feature without a specific reason.

**Recommended model:** Terra Medium.

## SX-003 · Create read-only diagnostic collector — P0

Build the first executable tool as a read-only collector that can export:

- DMI/kernel/module state;
- relevant hwmon/sysfs state;
- Bluetooth device/service inventory without secrets;
- PCIe/NVMe inventory;
- temperatures/health data;
- relevant kernel messages.

**Acceptance:** running it cannot modify fan, power, BLE, EC, filesystem, or storage state.

**Recommended model:** Terra Medium.

---

# Phase 1 — Frost Bay protocol proof of concept

## SX-FB-001 · Passive Frost Bay Bluetooth discovery — P0 / RESEARCH

With Frost Bay powered and Bluetooth enabled:

- identify advertised device name/address type;
- record advertisement/service UUIDs;
- enumerate GATT services, characteristics, descriptors, properties;
- determine which characteristics are readable/notifiable/writeable;
- collect passive notifications where possible without issuing hardware-control writes.

**Acceptance:** `docs/FROST_BAY.md` contains a reproducible, non-destructive discovery procedure and confirmed GATT map.

**Recommended model:** **Astra High**.

## SX-FB-002 · Static OneXConsole protocol archaeology — P0 / RESEARCH

Inspect publicly distributed OneXConsole binaries/resources for Frost Bay-specific:

- device-name strings;
- BLE UUIDs;
- characteristic constants;
- packet/message structures;
- telemetry labels;
- command/mode identifiers;
- range checks or safety logic.

Do not patch or redistribute proprietary binaries.

**Acceptance:** useful findings are documented with evidence and separated into CONFIRMED/LIKELY/HYPOTHESIS.

**Recommended model:** **Astra High**.

## SX-FB-003 · Known-good traffic correlation — P0 / RESEARCH

Only if passive/static analysis is insufficient, capture known-good OneXConsole ↔ Frost Bay behavior in a controlled Windows environment.

Change exactly one UI setting at a time, e.g. safe fan/pump/mode transitions, and correlate protocol differences.

**Acceptance:** at least one safe control command and one telemetry/status field are understood well enough to reproduce and validate.

**Recommended model:** **Astra High**.

## SX-FB-004 · Linux read-only Frost Bay client — P1

Implement discovery, connection, identity validation, notifications, and telemetry decode without control writes.

**Acceptance:** Linux reports the same confirmed status/telemetry as the known-good reference behavior.

**Recommended model:** Terra Medium.

## SX-FB-005 · Minimum safe Linux control POC — P1

Implement the smallest confirmed control operation with strict identity/range checks.

Start with a benign reversible setting, not maximum power or an aggressive cooling transition.

**Acceptance:** requested change is observed on hardware, restored cleanly, repeated multiple times, and protocol behavior is documented.

**Recommended model:** Astra High for first hardware control; Terra Medium afterward.

## SX-FB-006 · Frost Bay state machine and fault handling — P1

Model:

- disconnected;
- connecting;
- connected/unknown;
- healthy;
- degraded/fault;
- stale telemetry.

**Acceptance:** daemon never treats stale/disconnected state as healthy.

**Recommended model:** Terra Medium.

## SX-FB-007 · Liquid-power safety gate — P1

Determine how Super X power policy should react to Frost Bay disconnect/fault.

Do not assume a 120 W ceiling or fallback value from community anecdotes alone; verify hardware/platform behavior.

**Acceptance:** any liquid-only high-power profile requires a positive fresh cooler-health signal and fails back safely.

**Recommended model:** **Astra High** for investigation; Terra Medium for implementation.

---

# Phase 2 — Mini SSD root-cause investigation

## SX-SSD-001 · Establish Mini SSD baseline identity — P0 / RESEARCH

When the device is detected, record:

- PCI vendor/device IDs;
- PCIe link width/speed;
- NVMe controller/namespace identity;
- firmware revision;
- SMART/health log;
- temperature;
- power states/capabilities;
- filesystem and mount configuration used for testing.

**Acceptance:** a future failure can be compared to a known-good baseline.

**Recommended model:** Terra Medium.

## SX-SSD-002 · Build non-destructive state classifier — P0

Classify each sample as:

- `ABSENT` — PCIe endpoint missing;
- `PCIE_ONLY` — endpoint visible but usable NVMe namespace/controller missing;
- `NVME_PRESENT` — controller/block device present;
- `IO_DEGRADED` — device remains present but kernel/I/O errors occur;
- `HEALTHY` — passes current test criteria.

**Acceptance:** one command creates a timestamped diagnostic snapshot and state classification.

**Recommended model:** Terra Medium.

## SX-SSD-003 · Reproduce disappearance systematically — P0 / RESEARCH

Run a controlled matrix across repeated cycles:

- cold boot;
- warm reboot;
- idle;
- suspend/resume;
- normal sequential reads;
- controlled disposable write workload;
- post-load idle;
- thermal rise/cooldown.

Capture PCIe/NVMe/kernel/temperature state before and after each transition.

**Acceptance:** either a reproducible trigger is identified or enough negative evidence exists to narrow the failure domain.

**Recommended model:** **Astra High**.

## SX-SSD-004 · Determine failure layer — P0 / RESEARCH

Use evidence to discriminate among:

- physical seating/contact;
- slot power;
- PCIe link training;
- PCIe ASPM/power management;
- NVMe controller power state/reset;
- controller firmware;
- thermals;
- filesystem/I/O stack;
- defective hardware.

**Acceptance:** document the strongest supported root-cause hypothesis and ruled-out alternatives. Do not propose permanent mitigations until the failure layer is demonstrated.

**Recommended model:** **Astra High**.

## SX-SSD-005 · Test minimum mitigation — P1 / RESEARCH

Change one variable at a time based on SX-SSD-004 evidence.

Examples may include a specific power-management quirk, but only if the evidence points there.

**Acceptance:** mitigation survives a defined repeatability test and does not merely produce one successful boot.

**Recommended model:** Astra High.

## SX-SSD-006 · Reliability qualification — P1

Define a qualification suite before storing anything important on the Mini SSD.

Suggested minimum:

- repeated cold/warm boots;
- repeated suspend/resume;
- extended idle;
- sustained read workload;
- disposable sustained write/read verification;
- thermal observation;
- kernel log free of controller/link resets;
- checksum verification of test files.

**Acceptance:** results recorded in a test report. Passing once is insufficient.

**Recommended model:** Terra Medium.

## SX-SSD-007 · Storage health monitor — P2

Expose current Mini SSD state in Super X Helper and retain bounded recent error history.

**Acceptance:** user can see whether a disappearance was PCIe-, NVMe-, I/O-, or thermal-level where evidence permits.

**Recommended model:** Terra Medium.

---

# Phase 3 — Core daemon and CLI

## SX-CORE-001 · Choose implementation stack — P0

Evaluate language/toolkit choices against actual requirements:

- BlueZ BLE integration;
- DBus/polkit;
- sysfs/hwmon access;
- safe subprocess wrapper where unavoidable;
- packaging on Ubuntu;
- testability.

Rust is a strong default candidate but not a requirement.

**Acceptance:** short architecture decision record explains the selection.

**Recommended model:** Astra Medium or Terra High.

## SX-CORE-002 · Implement daemon skeleton — P1

Add:

- local-only API/DBus service;
- capability discovery;
- structured errors;
- event subscription;
- privilege boundary;
- logging without secrets.

**Recommended model:** Terra Medium.

## SX-CORE-003 · Platform backend — P1

Wrap confirmed Linux interfaces for fan, power, battery, thermals, and other chosen controls.

**Acceptance:** no arbitrary sysfs path or shell string can be supplied by the UI.

**Recommended model:** Terra Medium.

## SX-CORE-004 · Frost Bay backend — P1

Move confirmed Frost Bay protocol into typed production code with fixtures and range validation.

**Recommended model:** Terra Medium.

## SX-CORE-005 · Storage backend — P1

Integrate state classifier, telemetry, and read-only diagnostics into daemon.

**Recommended model:** Terra Medium.

## SX-CORE-006 · CLI — P1

Provide an initial troubleshooting/control surface such as:

```text
superxctl status
superxctl fan status
superxctl frostbay status
superxctl storage mini-ssd status
superxctl diagnostics export
```

Only expose write commands once their backend is production-qualified.

**Recommended model:** Terra Medium.

---

# Phase 4 — GUI control center

## SX-UI-001 · Dashboard — P1

Show:

- power/thermal state;
- internal fan state;
- Frost Bay state;
- Mini SSD state;
- active profile.

## SX-UI-002 · Performance page — P1

Expose confirmed power and CPU controls with validated ranges.

## SX-UI-003 · Cooling page — P1

Internal fan + Frost Bay control/telemetry, with health state visually distinct from requested control state.

## SX-UI-004 · Storage page — P1

Mini SSD presence, health, temperature, error state, reliability diagnostics, export button.

## SX-UI-005 · Profiles — P2

Declarative named profiles with transactional application and rollback on failure.

## SX-UI-006 · Game-aware profile switching — P2

Optional future integration. Detect launched games/processes and apply user-selected profiles without becoming a game launcher.

**Recommended model for Phase 4:** Terra Medium.

---

# Phase 5 — Hardening and packaging

## SX-HARD-001 · Hardware regression suite — P1

Opt-in tests for supported control paths.

## SX-HARD-002 · Safe startup/recovery — P1

Daemon crash/restart must not leave persistent unsafe assumptions about Frost Bay or power state.

## SX-HARD-003 · Permissions/polkit review — P1

Minimize root capability.

## SX-HARD-004 · Ubuntu packaging — P1

Package daemon, CLI, UI, service files, and permissions cleanly.

## SX-HARD-005 · Compatibility report — P2

Expose kernel/version/interfaces detected so bug reports are actionable.

## SX-HARD-006 · Broader ONEXPLAYER evaluation — P2

Only after Super X works reliably, identify which architecture pieces can support related ONEXPLAYER hardware without model-specific hacks leaking into shared code.

---

# Suggested first Astra mission

Do **not** ask Astra to build the whole application first.

The best initial mission is:

> On the actual Ubuntu Super X, establish a safe evidence-backed Frost Bay Bluetooth protocol map and implement a minimum read-only Linux client, continuing autonomously through passive discovery, static OneXConsole inspection, and bounded experimentation without blind writes.

The second best mission is:

> Build and execute the Mini SSD fault-isolation experiment until the disappearing drive is localized to PCIe enumeration, NVMe controller/namespace, I/O, thermal, power-management, firmware, or physical behavior with evidence strong enough to select one minimal next mitigation.

Those are the places where Astra's additional reasoning budget is most likely to buy something useful.