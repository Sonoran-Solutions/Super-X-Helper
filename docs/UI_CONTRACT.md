# Super X Helper — Frontend Contract

This is the stable surface the pre-Astra frontend should consume.

## Source of truth

Code:

- `src/superx_helper/contracts.py`
- `src/superx_helper/service.py`
- `src/superx_helper/client.py`
- `src/superx_helper/ui_manifest.py`

Frontend code must not import `platform.py`, `storage.py`, raw sysfs paths, or future Frost Bay protocol code.

## Capability record

Every feature is represented by a `CapabilityRecord` containing:

- `capability_id` — stable string key;
- `label`;
- `status`;
- `read_supported`;
- `write_supported`;
- `write_authorized`;
- `locally_validated`;
- `observed_value`;
- `desired_value`;
- `allowed_values` and/or numeric range/unit;
- `owner` and backend;
- `reason_unavailable`;
- warnings;
- `safety_state`;
- derived `can_write`.

The UI enables a mutating control only when `can_write == true`. A discovered sysfs node is not enough.

## Status semantics

- `CONFIRMED_LOCAL` — all behavior advertised by this record has passed local validation.
- `SUPPORTED_UNVERIFIED` — credible interface/source evidence exists, but the advertised operation has not passed the local production gate.
- `READ_ONLY` — telemetry/state is trustworthy; no production write is advertised.
- `RESEARCH_PENDING` — a separate evidence/reverse-engineering task is required.
- `UNAVAILABLE` — selected Linux stack currently does not expose the feature.
- `ERROR` — expected capability currently fails.

## Safety states

At minimum:

- `NORMAL`
- `WARNING`
- `NOT_QUALIFIED`
- `BLOCKED`
- `UNKNOWN`
- `ERROR`

`Mini SSD Reliability` is intentionally `NOT_QUALIFIED` before the deep-research/qualification track.

Frost Bay telemetry/control are intentionally `RESEARCH_PENDING` + `BLOCKED` before protocol research.

## Stable capability IDs

```text
performance.cpu_boost
performance.epp
performance.power_target
cooling.internal_fan
cooling.frost_bay.telemetry
cooling.frost_bay.control
display.brightness
display.mode
power.battery
power.charge_control
storage.mini_ssd.presence
storage.mini_ssd.reliability
device.rgb
device.controller_integration
diagnostics.export
```

Do not invent alternate strings in UI code.

## Page manifest

`ui_manifest.PAGES` defines the first application navigation:

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

Tier-1 frontend work should build these pages from the manifest/capability snapshot.

## Required pre-Astra rendering behavior

### Frost Bay

Render a visible disabled card/section:

```text
Frost Bay
Research pending
Linux protocol/health semantics not validated
```

Do not fake disconnected/zero telemetry as if a backend exists.

### Mini SSD

Presence/PCIe/NVMe telemetry can render normally, but reliability must remain visually distinct:

```text
Reliability: NOT QUALIFIED
Do not use as the only copy of important data
```

Enumeration or SMART success alone never changes this to healthy.

### Unverified controls

For `SUPPORTED_UNVERIFIED`, show observed values when available but disable writes and explain why. This lets the frontend be complete before hardware-validation passes finish.

## Client abstraction

The frontend depends on `ServiceClient.get_snapshot()`.

During early UI work use `LocalServiceClient`. Production will add a D-Bus implementation of the same contract.

The UI should not care whether a snapshot came from an in-process development client or the privileged D-Bus service.
