# Super X Helper — Design Document

## 1. Purpose

Super X Helper is a Linux-native control and diagnostics layer for the ONEXPLAYER Super X. It should expose the useful device-management capabilities normally associated with OneXConsole while adding two capabilities that are especially important on the liquid-cooled Super X:

1. Linux-native control and telemetry for the Frost Bay external liquid cooler.
2. Evidence-based diagnosis and monitoring for the removable Mini SSD reliability problem.

The design intentionally separates **hardware discovery/research** from **production control**. The project should not turn reverse-engineering guesses into persistent system behavior.

---

## 2. Product requirements

### 2.1 Core requirements

The eventual application should provide one place to view and control supported Super X functions such as:

- performance/power target;
- internal fan mode and speed/curve;
- CPU boost or related performance toggles where safely exposed;
- battery charge controls where supported;
- display configuration shortcuts where useful;
- RGB/device controls where a maintained Linux interface exists;
- Frost Bay presence, telemetry, mode, pump/fan controls, and fault state;
- Mini SSD presence, health, temperature, PCIe/NVMe error history, and reliability warnings.

### 2.2 Research requirements

The project must also be capable of gathering structured evidence from the real device:

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
- Never silently enable a high-power profile based only on an assumed Frost Bay state.
- Never run destructive storage tests against a filesystem containing important data.
- Never format, repartition, or overwrite the Mini SSD as part of an automatic diagnostic flow.
- Privileged operations must be explicit, narrow, validated, and logged.
- Hardware writes should have known ranges, known units, and safe fallback behavior.

---

## 3. Design principles

### 3.1 Thin privileged backend

The GUI should run unprivileged. A small privileged daemon owns only the operations that actually require elevated access.

```text
UI
│
│ authenticated local IPC
▼
SuperX Helper daemon
│
├── PlatformControl
├── FrostBayControl
└── StorageDiagnostics
```

Do not run the whole GUI as root.

### 3.2 Capability discovery instead of assumptions

Every backend reports capabilities:

```text
DeviceCapabilities
- fanControl
- fanTelemetry
- chargeLimit
- cpuPowerControl
- frostBayPresent
- frostBayControl
- frostBayTelemetry
- miniSsdPresent
- miniSsdTelemetry
- rgbControl
- displayControls
```

The UI renders what the current system can actually do.

This makes the project resilient across kernel versions and future Super X variants.

### 3.3 Prefer stable Linux interfaces

Preferred order:

1. upstream kernel/sysfs/hwmon interfaces;
2. stable DBus APIs;
3. maintained userspace libraries/tools;
4. narrowly wrapped existing command-line tools;
5. direct hardware/protocol access only when no maintained interface exists.

Direct EC access is a research tool, not the normal application architecture.

### 3.4 Separate desired state from observed state

For hardware controls, do not assume a successful write means the device actually entered that state.

Example:

```text
requested pump = 70%
observed pump  = 68%
status         = healthy
```

Where telemetry is unavailable, surface that limitation explicitly.

### 3.5 Fail-safe performance policy

A future 120 W liquid-cooled profile must depend on a positive, recent, validated Frost Bay health state.

Conceptually:

```text
LiquidHighPowerEligible =
    FrostBay.connected
    && FrostBay.protocolValidated
    && FrostBay.health == HEALTHY
    && FrostBay.telemetryFresh
```

If the cooler disconnects or health becomes unknown, Super X Helper should immediately request a safe non-liquid profile rather than leaving a stale high-power configuration active.

The exact safe target must be verified against the hardware before implementation.

---

## 4. Proposed architecture

```text
┌───────────────────────────────────────────────────────────┐
│                     Super X Helper UI                     │
│                                                           │
│ Dashboard · Performance · Cooling · Storage · Diagnostics │
└───────────────────────────┬───────────────────────────────┘
                            │
                       Local IPC/API
                            │
┌───────────────────────────▼───────────────────────────────┐
│                    superx-helperd                         │
│                                                           │
│  Policy / validation / capability discovery / event bus   │
└─────────────┬────────────────┬──────────────────┬─────────┘
              │                │                  │
       ┌──────▼──────┐  ┌──────▼──────┐   ┌──────▼──────┐
       │ Platform    │  │ Frost Bay   │   │ Storage     │
       │ backend     │  │ backend     │   │ backend     │
       └──────┬──────┘  └──────┬──────┘   └──────┬──────┘
              │                │                  │
      sysfs/hwmon/DBus       BlueZ             sysfs
      oxpec/RyzenAdj          BLE            PCIe/NVMe
              │                │                  │
       ONEXPLAYER EC       Frost Bay          Mini SSD
```

### 4.1 UI process

Responsibilities:

- display state;
- submit validated high-level requests;
- edit profiles;
- show diagnostics/history;
- never contain raw EC or BLE protocol logic.

Potential technologies should be evaluated after research. Good candidates include GTK/libadwaita for Ubuntu/GNOME integration or another Linux-native toolkit with reliable DBus support. The UI framework is intentionally not locked yet.

### 4.2 Daemon

Responsibilities:

- capability discovery;
- permission boundary;
- normalize backend state;
- validate ranges and transitions;
- apply profiles transactionally;
- own Frost Bay connection lifecycle;
- monitor Mini SSD state;
- persist safe user configuration;
- publish change events to the UI.

Possible implementation languages should prioritize safe systems integration, strong DBus/BLE libraries, and maintainability. Rust is a strong candidate, but the project should validate library/device requirements before committing.

### 4.3 Platform backend

Interfaces may include:

```text
PlatformBackend
- getCapabilities()
- getPowerState()
- setPowerTarget(watts)
- getInternalFanState()
- setInternalFanMode(mode)
- setInternalFanDuty(percent)
- getBatteryState()
- setChargePolicy(...)
- getThermalTelemetry()
```

Implementation should primarily wrap `oxpec`, hwmon/sysfs, standard power interfaces, and a narrowly-scoped RyzenAdj adapter when required.

### 4.4 Frost Bay backend

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

No method should be exposed until its underlying characteristic/command is confirmed experimentally.

The production backend must use named protocol fields and validated encoding, not magic byte arrays scattered through UI code.

### 4.5 Storage backend

```text
MiniSsdMonitor
- getPresenceState()
- getPciIdentity()
- getNvmeIdentity()
- getSmartHealth()
- getTemperature()
- getErrorCounters()
- getLinkState()
- runReadOnlyProbe()
- exportDiagnosticBundle()
```

A diagnostic session should timestamp and correlate:

- PCIe enumeration;
- NVMe namespace/controller presence;
- SMART/health data;
- AER/link errors where available;
- kernel messages;
- power-management state;
- temperatures;
- suspend/resume and reboot transitions.

---

## 5. Profile model

Profiles should be declarative user policy, not scripts.

Example:

```yaml
name: Balanced
power_target_w: 45
cpu_boost: true
internal_fan:
  mode: auto
frost_bay:
  mode: auto
  required: false
```

A future liquid profile might include:

```yaml
name: Liquid Performance
power_target_w: 120
frost_bay:
  required: true
  minimum_health: healthy
```

The daemon decides whether the requested profile is currently safe/available.

Do not put raw commands, file paths, BLE UUIDs, or EC register values in user profiles.

---

## 6. Diagnostics model

Diagnostics should generate human-readable and machine-readable results.

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

Default diagnostics must exclude unrelated personal files, Steam metadata, credentials, Bluetooth secrets, and filesystem content.

---

## 7. Research-to-production gate

A discovered control becomes production-supported only after:

1. the interface/protocol field is documented;
2. safe input range is known;
3. at least one round-trip or observable effect confirms it;
4. reset/disconnect behavior is known;
5. repeated tests produce consistent behavior;
6. a regression test or fixture can validate encoding/logic without hardware where practical;
7. the production implementation does not require broad raw-hardware privileges.

Use status labels in research docs:

- **CONFIRMED** — repeated direct evidence.
- **LIKELY** — strong evidence but incomplete validation.
- **HYPOTHESIS** — plausible and testable.
- **REJECTED** — contradicted by experiment.

---

## 8. Frost Bay research strategy

Preferred order:

1. Linux Bluetooth inventory and passive discovery.
2. GATT service/characteristic enumeration.
3. Notification/read observation without writes.
4. Static inspection of publicly distributed OneXConsole files for device names, UUIDs, command constants, telemetry labels, or protocol classes.
5. If needed, controlled known-good Windows captures while changing one setting at a time.
6. Reproduce only already-understood commands from Linux with bounded safe values.
7. Build protocol fixtures/tests.
8. Integrate with daemon.

Never start at step 6.

---

## 9. Mini SSD research strategy

The key question is not initially "how do we fix it?" but "where does it fail?"

State model:

```text
ABSENT
  └── no PCIe endpoint

PCIE_ONLY
  └── PCIe endpoint present; no usable NVMe controller/namespace

NVME_PRESENT
  └── controller and block device present

IO_DEGRADED
  └── device present but errors/timeouts/read-write failures occur

HEALTHY
  └── stable under the defined test suite
```

Experiments should isolate:

- cold boot;
- warm reboot;
- insertion only while fully powered off unless manufacturer documentation explicitly supports otherwise;
- idle periods;
- suspend/resume;
- normal reads;
- controlled disposable writes only when test data is backed up;
- thermal load;
- relevant PCIe/NVMe power-management changes one at a time.

A workaround is not considered solved until the failure remains absent across repeated cycles and meaningful usage duration.

---

## 10. Security and privileges

The daemon should expose a narrow local API. The UI asks for high-level actions such as `set_fan_duty(70)`, not `write('/sys/...', '178')`.

Recommended properties:

- root-owned daemon;
- unprivileged UI;
- DBus/polkit or equivalent authorization;
- no network listener by default;
- no shell command construction from UI strings;
- fixed executable paths/structured arguments for any external helper;
- bounded numeric ranges;
- explicit device identity checks before hardware writes.

---

## 11. Testing strategy

### Unit tests

- configuration/profile validation;
- backend capability normalization;
- BLE packet encode/decode fixtures;
- safe-range validation;
- Mini SSD state classification;
- diagnostics redaction.

### Integration tests

- fake sysfs/hwmon tree;
- mocked BlueZ device/service;
- recorded Frost Bay notification fixtures;
- captured NVMe/kernel event fixtures.

### Hardware tests

Hardware tests are explicit and opt-in. They should print what they intend to change before doing it and restore prior state where practical.

Never make a destructive Mini SSD test part of `test` or CI.

---

## 12. Version-one boundary

Version 0.1 should prioritize:

- reliable platform capability inventory;
- safe internal fan/power controls that use existing Linux interfaces;
- Frost Bay proof of control and basic telemetry;
- Mini SSD diagnostic/monitoring capability;
- one simple UI or CLI proving the architecture.

Do not block 0.1 on game-library features, broad ONEXPLAYER compatibility, cloud services, elaborate theming, or automatic per-game profile detection.