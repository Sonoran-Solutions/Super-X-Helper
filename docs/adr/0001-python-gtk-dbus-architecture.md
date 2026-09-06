# ADR-0001 — Python + GTK/libadwaita + system D-Bus architecture

**Status:** Accepted for the pre-Astra daily-driver milestone  
**Date:** 2026-09-06

## Context

The repository already has useful Python discovery/diagnostic code. The next milestone is a Linux-native daily-driver control center, not a rewrite. The application needs safe access to sysfs/hwmon, a narrow privileged boundary for future writes, Ubuntu-native UI behavior, and a stable contract that Frost Bay and Mini SSD research can plug into later.

## Decision

### Core/backend language

Keep **Python** as the v0.1 core. Do not migrate to Rust before an actual safety, performance, packaging, or library limitation is demonstrated.

The package is split conceptually into:

```text
hardware discovery / telemetry
        ↓
transport-neutral service facade
        ↓
system D-Bus adapter
        ↓
unprivileged UI client
```

The authoritative UI contract lives in `superx_helper.contracts`, not in GTK widgets, D-Bus XML, or raw sysfs paths.

### UI toolkit

Use **GTK 4 + libadwaita through PyGObject** for the Ubuntu-first desktop application.

Reasons:

- native GNOME/Ubuntu behavior;
- good adaptive layouts for tablet/desktop use;
- no embedded browser/runtime required;
- Gio provides the D-Bus primitives needed by both UI and service;
- a compact quick-access window can share the same application/process.

The Python core remains importable without GTK so diagnostics/tests stay usable on headless systems.

### Privilege boundary

Use a **root-owned `superx-helperd` systemd service on the system D-Bus** for production hardware writes.

Rules:

- UI always runs unprivileged;
- no network listener;
- mutating methods are explicit high-level operations, never arbitrary file paths/commands;
- mutating methods require capability validation and polkit authorization;
- discovery of a writable path does not authorize a write;
- read-only telemetry should use the least privilege possible;
- Frost Bay raw protocol bytes never cross the UI API.

During UI development, `LocalServiceClient` may call the transport-neutral service facade in-process. A later D-Bus client must implement the same frontend-facing interface.

### D-Bus API direction

The first adapter should expose a versioned structured snapshot corresponding to `CapabilitySnapshot` plus a narrow mutation API.

Conceptual surface:

```text
GetSnapshot() -> CapabilitySnapshot
SetCapability(capability_id, value) -> OperationResult
ApplyProfile(profile) -> ProfileResult          # later
ExportDiagnostics(options) -> diagnostic result # later

signal SnapshotChanged(changed_capability_ids)
```

The D-Bus adapter serializes typed records; it must not become a second source of capability semantics.

### Telemetry/events

The daemon owns hardware polling. It publishes normalized state changes rather than making every widget poll sysfs independently.

Initial target:

- low-frequency background telemetry appropriate for a settings application;
- faster refresh only while the quick-access panel/dashboard is visible if needed;
- D-Bus change signals for UI updates;
- expensive diagnostics such as SMART/journal collection remain explicit operations rather than high-frequency polling.

### Configuration and profiles

User profiles/settings live under the XDG user config directory, initially as versioned JSON:

```text
~/.config/superx-helper/
  settings.json
  profiles.json
```

Profiles contain only high-level policy. They never contain shell commands, sysfs paths, EC registers, or BLE packets.

The privileged daemon validates all incoming profile actions independently.

### Packaging

Target a normal **Ubuntu `.deb`** first.

Expected package pieces:

- Python package;
- GTK/libadwaita UI entry point;
- `superx-helperd` systemd unit;
- D-Bus service/policy files;
- polkit policy/rules;
- desktop entry and icons;
- CLI/diagnostic entry points.

GTK/PyGObject should use distro packages (`python3-gi`, GTK4/libadwaita GIR packages) rather than attempting to vendor the desktop stack through pip.

Flatpak/AppImage can be evaluated later; they are not the first packaging target because privileged host integration is central to this app.

### Quick-access panel

Implement the quick-access experience as a second compact GTK/libadwaita window backed by the same service client and capability contract.

Opening the panel is an integration concern, not a new input driver. Prefer an existing Super X/HHD/InputPlumber/desktop shortcut path. If no stable mechanism exists, ordinary global shortcut support is acceptable for v0.1.

## Consequences

### Positive

- preserves useful existing Python work;
- gives Tier-1 frontend models a stable, small contract;
- keeps hardware writes out of UI code;
- makes `RESEARCH_PENDING` Frost Bay and `NOT_QUALIFIED` Mini SSD states natural data rather than special-case widgets;
- leaves room to replace an individual backend later without rewriting the UI.

### Tradeoffs

- Python is not as compile-time strict as Rust, so typed records, tests and narrow adapters matter;
- system D-Bus/polkit adds packaging work;
- PyGObject is best installed from Ubuntu packages rather than a pure pip environment.

## Revisit conditions

Reconsider the backend language only if measured evidence shows Python cannot safely/reliably satisfy BLE, telemetry, privilege, latency, or packaging requirements. Do not rewrite because another language is aesthetically preferable.
