# Super X Helper — Design Document

## 1. Purpose

Super X Helper is a Linux-native control/diagnostics layer for the ONEXPLAYER Super X. The pre-Astra milestone prioritizes a real daily-driver application around ordinary Linux-supported functionality while keeping Frost Bay and Mini SSD reliability as explicit later research backends.

## 2. Accepted architecture

ADR: [`docs/adr/0001-python-gtk-dbus-architecture.md`](docs/adr/0001-python-gtk-dbus-architecture.md)

```text
┌─────────────────────────────────────────────────────────────┐
│ GTK4/libadwaita UI (unprivileged)                           │
│ Dashboard · Performance · Cooling · Display · Power · ...   │
└────────────────────────────┬────────────────────────────────┘
                             │ ServiceClient
                             │ system D-Bus in production
┌────────────────────────────▼────────────────────────────────┐
│ Python superx-helperd service facade                        │
│ capability normalization · validation · policy · events     │
└──────────────┬───────────────────┬──────────────────────────┘
               │                   │
       Platform backend      Storage backend       Frost Bay backend (later)
               │                   │                      │
       sysfs/hwmon/DRM       PCIe/NVMe             BlueZ/protocol
```

### Decisions

- Python remains the core/backend language for v0.1.
- GTK4/libadwaita through PyGObject is the UI toolkit.
- Production writes go through a root-owned system D-Bus service and polkit.
- The UI never receives raw writable paths or BLE packets.
- Ubuntu `.deb` is the first packaging target.
- Profiles/settings use versioned high-level JSON under the user's XDG config directory.
- Quick access is another GTK window using the same client/contract.

## 3. Capability contract

Code source of truth:

- `contracts.py`
- `service.py`
- `client.py`
- `ui_manifest.py`

A `CapabilityRecord` exposes:

- stable capability ID;
- status;
- read/write support;
- write authorization;
- local validation;
- observed/desired state;
- range/options/unit;
- owner/backend;
- reason unavailable;
- warnings;
- safety state;
- derived `can_write`.

Status vocabulary:

```text
CONFIRMED_LOCAL
SUPPORTED_UNVERIFIED
READ_ONLY
RESEARCH_PENDING
UNAVAILABLE
ERROR
```

Discovery does not grant write authority.

## 4. Privilege model

The GUI is never run as root.

The future D-Bus service exposes narrow high-level methods conceptually:

```text
GetSnapshot()
SetCapability(capability_id, value)
ApplyProfile(profile)       # later
ExportDiagnostics(options)  # later
```

Requirements for a mutation:

1. stable capability ID recognized;
2. interface exists;
3. input type/range/options valid;
4. capability has passed local production validation;
5. current policy authorizes the write;
6. polkit authorization succeeds where required;
7. observed state verifies the request;
8. prerequisites/failure handling succeed.

No UI-controlled shell commands or file paths.

## 5. Current backend state

### Platform

The low-level discovery layer can identify boost, EPP, backlight, `oxpec` hwmon presence and Mini SSD presence.

All real platform writes default to **unauthorized**. Tests may explicitly authorize fake sysfs fixtures, but production authorization is empty until live validation occurs.

### Storage

Mini SSD presence follows:

```text
ABSENT
  no known PCIe endpoint

PCIE_ONLY
  endpoint exists but no usable NVMe namespace/block device

NVME_PRESENT
  controller + namespace/block device visible
```

This is a presence model, not a reliability verdict.

`Mini SSD Reliability` remains `NOT_QUALIFIED` until the later experimental qualification track.

### Frost Bay

Both Frost Bay telemetry and control are `RESEARCH_PENDING` and `BLOCKED` pre-Astra. No fake zero/disconnected telemetry is emitted as if protocol support existed.

## 6. Diagnostics

Default diagnostics are read-only and privacy-reduced.

Possible evidence:

- DMI/kernel/modules;
- hwmon/thermal/power;
- battery/display;
- PCIe/NVMe controller + namespaces + link;
- allow-listed SMART/error fields;
- filtered relevant kernel messages;
- cached target-like BlueZ device/service data without scanning.

Unique SSD serials and Bluetooth addresses are redacted by default.

## 7. UI design contract

Navigation is defined by `ui_manifest.PAGES`:

```text
Dashboard
Performance
Cooling
Display
Power / Battery
Storage
Profiles
Diagnostics
```

The frontend depends only on `ServiceClient` and contract types. It does not import hardware backends.

### Disabled-state UX is first-class

The complete UI exists before every backend is writable.

Examples:

```text
Internal Fan
Supported by oxpec; live write validation pending
[controls disabled]
```

```text
Frost Bay
Research pending
[controls disabled]
```

```text
Mini SSD Reliability
NOT QUALIFIED
```

This allows later research to activate existing UI surfaces rather than forcing redesign.

## 8. Profiles

Profiles are declarative high-level policy, never scripts.

Example:

```json
{
  "schema_version": 1,
  "name": "Balanced",
  "settings": {
    "performance.cpu_boost": true,
    "performance.epp": "balance_performance"
  }
}
```

`Liquid Performance` may exist as a disabled profile but cannot become applicable until Frost Bay health/fallback semantics are confirmed.

Multi-setting mutations require transactional behavior/rollback where practical before production use.

## 9. Research-to-production gate

A write capability becomes `CONFIRMED_LOCAL` / writable only after:

1. interface/protocol semantics documented;
2. safe range/options known;
3. direct local effect verified;
4. observed state matches request;
5. prerequisite/failure behavior understood;
6. recovery/rollback behavior defined where safety needs it;
7. repeated test behavior is consistent;
8. regression tests/fixtures exist where practical;
9. privilege scope remains narrow.

## 10. Testing

Default CI/test runs use fake sysfs/mocked data and never require physical Super X hardware.

Current hardened suite includes coverage for:

- Mini SSD presence layers and namespaces;
- redaction;
- unverified controls remaining disabled;
- write verification mismatch;
- fan prerequisite failure;
- Frost Bay research state;
- Mini SSD qualification state;
- UI page manifest.

Hardware-changing tests remain explicit and opt-in.

## 11. Pre-Astra version boundary

Before deep research the application should already provide:

- polished GTK shell/dashboard;
- read-only telemetry pages;
- locally validated ordinary controls as they pass the production gate;
- profiles;
- quick access;
- diagnostics/export;
- basic Mini SSD presence/link/temp information with `NOT_QUALIFIED` reliability;
- Frost Bay placeholder as `RESEARCH_PENDING`.

Frost Bay protocol support and Mini SSD reliability qualification are **not** blockers for building/using the majority of the application.
