# Pre-Astra Daily-Driver Checkpoint

## Purpose

Before spending premium research-model budget on Frost Bay protocol reverse engineering or the Mini SSD reliability investigation, Super X Helper should already be useful as a Linux-native replacement for the ordinary OneXConsole features that can be implemented with known Linux interfaces.

The checkpoint exists to separate two classes of work:

```text
KNOWN / INTEGRATION WORK
- performance controls
- internal fan control
- battery telemetry
- display controls
- profiles
- quick access
- diagnostics
- basic Mini SSD presence/temperature/link state

UNKNOWN / RESEARCH WORK
- Frost Bay BLE protocol + health/control semantics
- Mini SSD disappearance/root cause + reliability qualification
```

Astra should be reserved for the second class.

## Product target

The pre-Astra build should feel like a real daily-driver application, not a hardware research notebook with buttons.

Suggested primary navigation:

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

A compact quick-access panel should expose the controls most useful while gaming.

## Capability-driven UI

The UI must render backend capability state instead of assuming every control exists.

Recommended normalized states:

- `AVAILABLE_READ_WRITE` — locally validated telemetry and control.
- `READ_ONLY` — trustworthy telemetry exists; control is unavailable or not yet validated.
- `SUPPORTED_UNVERIFIED` — source/interface evidence exists, but this exact hardware path has not passed the production gate.
- `RESEARCH_PENDING` — a separate evidence/reverse-engineering task is required.
- `UNAVAILABLE` — current Linux stack does not expose the capability.
- `ERROR` — capability is expected but currently failing.

These states are not permissions. The backend must independently authorize every write.

## Dashboard

Display at least:

- active profile;
- CPU/APU and GPU temperature where available;
- package/GPU power where useful;
- internal fan state;
- battery percentage/charge state;
- current internal display mode;
- Mini SSD presence + temperature/link data;
- Frost Bay placeholder/status;
- warnings/errors requiring attention.

Pre-Astra examples:

```text
Frost Bay
RESEARCH PENDING
Linux control protocol not yet validated
```

```text
Mini SSD
Present · PCIe Gen4 x2 · 45 °C
Reliability: NOT QUALIFIED
Do not use as the only copy of important data
```

## Performance page

Expose only validated controls, potentially including:

- CPU boost;
- AMD EPP/performance preference;
- package/APU power target if a production-qualified interface is established;
- current power/thermal state;
- profile selection.

The application may define a future `Liquid Performance` profile but it must remain unavailable until Frost Bay health semantics and safe fallback behavior are confirmed.

## Cooling page

### Internal cooling

Once `oxpec` behavior is validated on the actual Super X:

- current mode;
- current fan duty/RPM where available;
- Automatic / Quiet / Performance / Custom presets;
- custom fan curve if safe enforcement/rollback is implemented;
- clear desired-vs-observed state;
- recovery to firmware/EC automatic control when Super X Helper stops owning the fan.

### Frost Bay

Reserve a section/card in the same page before the protocol exists. It must be visibly disabled or `RESEARCH_PENDING`; do not hide the future architecture and do not simulate telemetry.

After research, the same UI should activate from backend capabilities rather than require a separate redesign.

## Display page

Where supported by the active Ubuntu display stack:

- brightness;
- resolution;
- refresh rate;
- VRR status/toggle if a reliable compositor/DRM control path exists;
- connected display state.

Prefer compositor-owned APIs and avoid competing with desktop display management.

## Power / Battery page

Show:

- percentage;
- charge/discharge status;
- battery capacity/health telemetry;
- performance preference/boost context;
- charge limit/bypass charging only if a trustworthy Linux control path is proven.

Unsupported controls should be labeled explicitly rather than omitted or guessed.

## Controller / vibration / gyro

Super X Helper should normally integrate with the maintained owner of these functions (HHD, InputPlumber, Steam, etc.) instead of creating a competing input stack.

UI exposure is desirable only when a stable integration API exists.

## RGB

RGB is desirable but not a pre-Astra blocker if it becomes its own proprietary protocol reverse-engineering problem.

Order of attack:

1. maintained Linux interface/project;
2. standard HID/USB interface with documented semantics;
3. Tier-3 static/reverse-engineering pass if required;
4. do not spend Tier-4 budget unless RGB unexpectedly becomes important enough to justify it.

## Profiles

Profiles should be high-level declarative policy.

Example:

```yaml
name: Balanced
cpu_boost: true
epp: balance_performance
power_target_w: 45
internal_fan:
  mode: auto
display:
  refresh_hz: 120
```

A future liquid profile can exist in configuration/UI while unavailable:

```yaml
name: Liquid Performance
requires:
  frost_bay_health: healthy
```

Profiles must not contain arbitrary paths, shell commands, EC registers, or raw BLE payloads.

Multi-setting profile application should be transactional where practical and report partial failure clearly.

## Quick-access experience

A core pre-Astra requirement is reducing terminal/settings hopping during games.

A compact panel should make common actions fast:

```text
Current profile
Power target (when supported)
Fan mode
Brightness
Refresh rate
CPU/GPU temperatures
Battery
```

Prefer existing controller/button event ownership rather than writing a new input driver merely to open the panel.

## Storage page before deep research

The Mini SSD page should already provide read-only facts:

- PCIe presence;
- NVMe controller/namespace presence;
- model/firmware with public-output redaction as appropriate;
- link speed/width;
- temperature;
- SMART/error telemetry where available;
- current presence classification;
- diagnostics/export.

It must **not** display `HEALTHY` merely because the device currently enumerates or SMART reports no fault. Until the reliability test passes, use `NOT_QUALIFIED`.

## Diagnostics

The GUI should expose the same trustworthy diagnostic collector used by research agents.

Default exported diagnostics should redact unnecessary unique hardware identifiers, Bluetooth addresses, usernames, credentials and unrelated personal data.

## Model handoff plan

### Foundation review

**GPT-5.6 Terra Medium**

- audit Gemini Flash scaffolding;
- finish the read-only evidence layer;
- establish the capability contract;
- validate/disable provisional write paths;
- select practical daemon/UI architecture.

### Bulk application build

**Gemini 3.8 Flash / DeepSeek V4 Flash**

- UI pages/components;
- settings/forms;
- profile editor;
- telemetry cards;
- tests/fixtures;
- documentation;
- mechanical backend wiring after contracts are defined.

### Serious integration

**GPT-5.6 Terra Medium**

- privileged boundary;
- transactional profiles;
- safe sysfs/DBus integration;
- hardware-write correctness;
- review of Flash-tier output.

### Unexpected hard ordinary feature

**DeepSeek V4 Pro High**

Use for difficult RGB/HID/static archaeology or a stubborn cross-layer integration problem before escalating to Tier 4.

### Deep research

**GPT-6 Astra High**

Only after the checkpoint, for:

1. Frost Bay protocol semantics + first safe proof-of-control.
2. Mini SSD fault isolation + evidence-backed mitigation experiment.

Astra should inherit a concise evidence packet and an already-defined backend/UI contract.

## Exit criteria

The checkpoint passes when:

- the application is pleasant enough to use instead of separate terminal commands for normal Super X controls;
- CPU/performance, internal fan, display, battery, diagnostics and profiles are integrated where Linux support exists;
- the quick-access workflow exists;
- basic Mini SSD telemetry is visible but reliability is explicitly unqualified;
- Frost Bay has a first-class UI/backend placeholder but no guessed protocol implementation;
- ordinary unresolved features are either documented follow-ups or explicitly classified as separate research problems;
- no Tier-4 work is required to use the majority of the application.

After this gate, Frost Bay and Mini SSD research can proceed independently without forcing a redesign of the application.