# Super X Helper — Design Document

## 1. Purpose

Super X Helper is a Linux-native control and diagnostics layer for the ONEXPLAYER Super X. It should expose the useful device-management capabilities normally associated with OneXConsole while keeping research-heavy unknowns isolated behind explicit capability states.

The project has three goals:

1. provide a polished daily-driver Linux control center for every ordinary feature already available through known Linux interfaces;
2. add Linux-native Frost Bay liquid-cooler support after its Bluetooth protocol is evidence-backed;
3. diagnose and eventually qualify/mitigate the removable Mini SSD reliability problem.

The immediate architecture target is a **pre-Astra daily-driver build**. The UI, backend contracts, profile model, diagnostics and normal platform controls should be complete before premium research effort is spent on Frost Bay and Mini SSD root-cause work.

---

## 2. Product requirements

### 2.1 Pre-Astra core requirements

The application should provide one place to view/control supported Super X functions such as:

- performance preference, CPU boost and validated power targets;
- internal fan mode, duty/RPM and safe curves where `oxpec` behavior is locally validated;
- battery telemetry and charge/bypass controls only where supported;
- display brightness/resolution/refresh/VRR where a stable Linux interface exists;
- controller/vibration/gyro integration through maintained Linux owners;
- RGB when an existing or reasonably understood Linux interface exists;
- declarative system profiles;
- a compact quick-access panel;
- Mini SSD presence, PCIe/NVMe state, temperature and read-only diagnostics;
- Frost Bay placeholder/status with `RESEARCH_PENDING` state until protocol work completes.

### 2.2 Research requirements

The project must also gather structured evidence from the real device:

- hardware inventory;
- kernel/interface inventory;
- BLE/GATT discovery and bounded capture;
- PCIe/NVMe state snapshots;
- kernel journal extraction;
- controlled before/after experiments;
- repeatable test reports.

### 2.3 Safety requirements

- Never blindly write undocumented EC registers.
- Never blindly write unknown BLE characteristics.
- Never silently enable a liquid-only high-power profile based on an assumed Frost Bay state.
- Never run destructive storage tests against a filesystem containing important data.
- Never format, repartition, overwrite or firmware-update the Mini SSD as part of an automatic diagnostic flow.
- Privileged operations must be explicit, narrow, validated and logged.
- Hardware writes require known ranges/units plus defined failure/rollback behavior.
- A capability being discoverable does not itself authorize a write.

---

## 3. Design principles

### 3.1 Thin privileged backend

The GUI runs unprivileged. A small privileged service owns only operations that require elevated access.

```text
UI
│
│ authenticated local IPC
▼
Super X Helper daemon/service
│
├── PlatformControl
├── FrostBayControl
└── StorageDiagnostics
```

Do not run the GUI as root.

### 3.2 Capability discovery instead of assumptions

Backends publish a normalized capability state rather than booleans that imply too much.

```text
CapabilityState
├── id
├── availability
├── read_supported
├── write_supported
├── locally_validated
├── observed_value
├── desired_value
├── source/owner
├── reason_unavailable
└── safety/health metadata where relevant
```

Recommended UI-facing states:

- `AVAILABLE_READ_WRITE`
- `READ_ONLY`
- `SUPPORTED_UNVERIFIED`
- `RESEARCH_PENDING`
- `UNAVAILABLE`
- `ERROR`

This allows the application to include Frost Bay and Mini SSD reliability from day one without pretending those problems are solved.

### 3.3 Capability is not authorization

The fact that a writable sysfs file exists does not mean Super X Helper is currently allowed to mutate it.

Write authorization may additionally depend on:

- local hardware validation status;
- selected ownership policy;
- conflicting daemon detection;
- privilege/polkit authorization;
- current safety state;
- rollback availability;
- feature-specific research-to-production gate.

### 3.4 Prefer stable Linux interfaces

Preferred order:

1. upstream kernel/sysfs/hwmon interfaces;
2. stable DBus/compositor APIs;
3. maintained userspace libraries/tools;
4. narrowly wrapped existing command-line tools;
5. direct hardware/protocol access only when no maintained interface exists.

Direct EC/BLE protocol access is a research/production backend concern, never UI logic.

### 3.5 Separate desired state from observed state

A successful write syscall is not proof the device reached the requested state.

```text
requested fan = 70%
observed fan  = 69%
write result  = accepted
state         = confirmed/healthy
```

Backends must compare requested and observed state where an observable value exists. If verification is impossible, surface that limitation explicitly.

### 3.6 Fail-safe performance policy

A future liquid-cooled high-power profile must depend on a positive, recent, validated Frost Bay health state.

```text
LiquidHighPowerEligible =
    FrostBay.connected
    && FrostBay.protocolValidated
    && FrostBay.health == HEALTHY
    && FrostBay.telemetryFresh
```

Before Frost Bay research completes, the profile may exist in UI/configuration but is **unavailable**.

If the cooler disconnects or health becomes unknown after later activation, the daemon should request a verified safe non-liquid fallback.

---

## 4. Proposed architecture

```text
┌──────────────────────────────────────────────────────────────┐
│                     Super X Helper UI                        │
│ Dashboard · Performance · Cooling · Display · Power          │
│ Storage · Profiles · Diagnostics · Quick Access              │
└────────────────────────────┬─────────────────────────────────┘
                             │
                        Local IPC/API
                             │
┌────────────────────────────▼─────────────────────────────────┐
│                    superx-helper service                     │
│ capability normalization · policy · validation · event bus   │
└──────────────┬─────────────────┬──────────────────┬──────────┘
               │                 │                  │
        ┌──────▼──────┐   ┌──────▼──────┐   ┌──────▼──────┐
        │ Platform    │   │ Frost Bay   │   │ Storage     │
        │ backend     │   │ backend     │   │ backend     │
        └──────┬──────┘   └──────┬──────┘   └──────┬──────┘
               │                 │                  │
       sysfs/hwmon/DBus        BlueZ             sysfs
       oxpec/power/display      BLE             PCIe/NVMe
```

### 4.1 UI process

Responsibilities:

- display capability and observed state;
- submit validated high-level requests;
- edit profiles;
- show diagnostics/history;
- render unavailable/read-only/research-pending states clearly;
- never contain raw EC, BLE, sysfs or NVMe mutation logic.

The UI should feel like a normal control center rather than a research notebook. See [`docs/PRE_ASTRA_CHECKPOINT.md`](docs/PRE_ASTRA_CHECKPOINT.md).

### 4.2 Service/daemon

Responsibilities:

- capability discovery;
- permission boundary;
- normalize backend state;
- validate ranges/transitions;
- apply profiles transactionally;
- persist safe user configuration;
- publish change events to UI/quick-access views;
- later own Frost Bay connection lifecycle;
- monitor Mini SSD read-only state.

Do not rewrite existing Python scaffolding purely for language preference. Choose the production stack based on actual DBus/BlueZ/sysfs/packaging requirements and migration cost; record the decision in an ADR.

### 4.3 Platform backend

```text
PlatformBackend
- getCapabilities()
- getPowerState()
- setPowerTarget(watts)           # only if production-qualified
- getInternalFanState()
- setInternalFanMode(mode)        # only if production-qualified
- setInternalFanDuty(percent)     # only if production-qualified
- getBatteryState()
- setChargePolicy(...)            # only if supported
- getDisplayState()
- setBrightness(...)
- getThermalTelemetry()
```

Implementation primarily wraps `oxpec`, hwmon/sysfs, standard power/display interfaces and narrowly scoped maintained helpers when required.

A failure to enter a prerequisite state (for example, fan manual mode) must abort the dependent write.

### 4.4 Frost Bay backend

Pre-Astra, the backend is a capability placeholder that reports `RESEARCH_PENDING` and performs no guessed writes.

After protocol research:

```text
FrostBayBackend
- scan()
- connect()
- disconnect()
- getProtocolIdentity()
- subscribeTelemetry()
- getState()
- setMode(...)
- setPump(...)
- setFan(...)
```

No method becomes production-supported until its characteristic/command semantics are confirmed experimentally.

### 4.5 Storage backend

Pre-Astra responsibilities are read-only:

```text
MiniSsdMonitor
- getPresenceState()
- getPciIdentity()
- getNvmeIdentity()
- getSmartHealth()
- getTemperature()
- getErrorCounters()
- getLinkState()
- exportDiagnosticBundle()
- getQualificationState()   # NOT_QUALIFIED until research passes
```

The UI must not map `NVME_PRESENT` or a clean SMART result directly to `HEALTHY`.

Later research correlates PCIe enumeration, NVMe controller/namespace, SMART/error logs, kernel messages, power state, thermals and reboot/suspend transitions.

---

## 5. UI information architecture

### 5.1 Dashboard

At-a-glance current profile, CPU/GPU thermals/power, fan, battery, display, Mini SSD status, Frost Bay status and important warnings.

### 5.2 Performance

Validated CPU boost/EPP/power controls plus observed telemetry. `Liquid Performance` exists as a disabled capability-dependent profile before Frost Bay research.

### 5.3 Cooling

Internal fan controls/curves after `oxpec` validation. Frost Bay occupies a separate card/section and remains `RESEARCH_PENDING` until its backend becomes available.

### 5.4 Display

Brightness, resolution, refresh and VRR where supported by compositor/DRM APIs.

### 5.5 Power / Battery

Battery telemetry, supported charge policy and links/context for performance behavior. Unsupported charge/bypass controls are visible as unavailable rather than guessed.

### 5.6 Storage

Mini SSD PCIe/NVMe presence, link, temperature, read-only health/error telemetry, diagnostic export and explicit reliability qualification state.

### 5.7 Profiles

Named high-level system policies with transactional application/rollback where practical.

### 5.8 Quick access

Compact high-frequency controls/telemetry intended for use while gaming. Integrate with existing input ownership rather than implementing a new controller driver solely to open the panel.

---

## 6. Profile model

Profiles are declarative user policy, not scripts.

```yaml
name: Balanced
power_target_w: 45
cpu_boost: true
epp: balance_performance
internal_fan:
  mode: auto
display:
  refresh_hz: 120
```

Future liquid profile:

```yaml
name: Liquid Performance
requires:
  frost_bay_health: healthy
```

The daemon decides whether the requested profile is currently available/safe.

Do not put raw commands, file paths, BLE UUIDs, EC register values or packet bytes in user profiles.

---

## 7. Diagnostics model

Diagnostics generate human-readable and machine-readable results.

Suggested bundle:

```text
diagnostics/
├── summary.json
├── hardware.json
├── kernel.txt
├── platform-controls.json
├── frost-bay.json
├── mini-ssd.json
└── journal-kernel.txt
```

Default diagnostics must exclude/redact unrelated personal files, Steam metadata, credentials, Bluetooth secrets/addresses, usernames and unnecessary unique device serials.

---

## 8. Research-to-production gate

A discovered/readable control becomes production-supported only after:

1. the interface/protocol field is documented;
2. safe input range is known;
3. at least one round-trip or observable effect confirms it;
4. failure/reset/disconnect behavior is known where relevant;
5. repeated tests produce consistent behavior;
6. tests/fixtures validate logic without hardware where practical;
7. the production implementation does not require broad raw-hardware privileges;
8. the UI capability state is upgraded explicitly from `SUPPORTED_UNVERIFIED` or `RESEARCH_PENDING`.

Research confidence labels remain:

- **CONFIRMED**
- **LIKELY**
- **HYPOTHESIS**
- **REJECTED**

---

## 9. Frost Bay research strategy

Only after the pre-Astra checkpoint:

1. cheap-model passive Bluetooth discovery/GATT inventory;
2. Tier-2 review of captures;
3. DeepSeek V4 Pro static OneXConsole archaeology;
4. hand curated evidence to Astra High;
5. minimum safe experiments for unresolved semantics;
6. read-only client;
7. first benign reversible control;
8. typed protocol implementation and production integration.

Astra should solve remaining unknowns, not spend its context rediscovering the Super X baseline.

---

## 10. Mini SSD research strategy

Pre-Astra UI shows basic read-only telemetry and `NOT_QUALIFIED` reliability.

The deep-research question remains: **where does it fail?**

```text
ABSENT
  └── no PCIe endpoint

PCIE_ONLY
  └── PCIe endpoint present; no usable NVMe controller/namespace

NVME_PRESENT
  └── controller + namespace/block device present

IO_DEGRADED
  └── device remains present but errors/timeouts occur

QUALIFIED
  └── stable under the defined repeatability suite
```

The investigation isolates cold/warm boot, idle, suspend/resume, safe reads, explicitly disposable writes, thermal behavior and evidence-backed power-management changes one at a time.

A workaround is not solved until repeated qualification passes.

---

## 11. Security and privileges

The service exposes a narrow local API. The UI requests `set_fan_duty(70)`, never `write('/sys/...', '178')`.

Recommended properties:

- root-owned or narrowly privileged service;
- unprivileged UI;
- DBus/polkit or equivalent authorization;
- no network listener by default;
- no shell command construction from UI strings;
- fixed executable paths/structured arguments for helpers;
- bounded numeric ranges;
- explicit device/capability identity checks before writes;
- conflicting-daemon/ownership policy before taking control.

---

## 12. Testing strategy

### Unit tests

- configuration/profile validation;
- capability normalization/state transitions;
- desired-vs-observed verification;
- prerequisite write failure handling;
- safe-range validation;
- Mini SSD classification;
- diagnostics redaction.

### Integration tests

- fake sysfs/hwmon tree;
- mocked DBus/compositor interactions;
- mocked BlueZ device/service;
- later Frost Bay notification fixtures;
- captured NVMe/kernel event fixtures.

### Hardware tests

Hardware tests are explicit and opt-in. Print intended changes before execution and restore prior state where practical.

Never make a destructive Mini SSD test part of normal `test` or CI.

---

## 13. Milestones

### Pre-Astra daily-driver checkpoint

Required:

- trustworthy diagnostics and capability model;
- polished dashboard/application shell;
- confirmed platform/performance controls;
- confirmed internal fan controls;
- display/battery integration where available;
- profiles;
- quick-access workflow;
- Mini SSD basic telemetry with `NOT_QUALIFIED` reliability;
- Frost Bay visible as `RESEARCH_PENDING`.

### Research-integrated release

Then add:

- Frost Bay telemetry/control + fault handling;
- liquid profile gating;
- evidence-backed Mini SSD reliability/mitigation state.

Do not block the pre-Astra milestone on game-library functionality, broad ONEXPLAYER compatibility, cloud services or elaborate theming.