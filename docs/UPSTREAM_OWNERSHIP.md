# Super X Helper — Upstream Controls & Ownership Reference

**Status:** reviewed capability/ownership baseline; write paths are not implicitly production-qualified.

## Ownership policy

1. Prefer stable upstream kernel/sysfs/hwmon interfaces.
2. Integrate with maintained userspace owners such as HHD/InputPlumber instead of duplicating controller stacks.
3. Keep raw/proprietary protocol ownership inside a dedicated backend only when no maintained interface exists.
4. Discovery and authorization are separate. Finding a writable node never grants the app permission to use it.

## Current matrix

| Subsystem | Primary Linux owner/interface | Current state | Super X Helper role |
|---|---|---|---|
| Internal fan | `oxpec` / hwmon | `SUPPORTED_UNVERIFIED` on captured host; module present but not loaded during baseline | normalize telemetry/control after explicit live validation |
| CPU boost | Linux cpufreq | observed/readable; write unverified | profile-facing adapter after live write validation |
| EPP | `amd-pstate-epp` | observed/readable; write unverified | profile-facing adapter after live write validation |
| Package/APU power target | powercap/RyzenAdj candidate paths | mechanism not production-selected | choose one evidence-backed adapter/range |
| Battery telemetry | power_supply | `READ_ONLY`, locally observed | display telemetry |
| Charge limit/bypass | unresolved | `UNAVAILABLE` until proven | do not guess |
| Display telemetry | DRM/amdgpu | `READ_ONLY`, locally observed | display state |
| Brightness | amdgpu backlight | read observed; write unverified | enable only after session/live validation |
| Resolution/refresh/VRR writes | compositor/DRM | mutation path unverified | integrate without fighting compositor |
| Controller/gyro/vibration | HHD/InputPlumber/Steam/kernel input | external maintained owner preferred | integrate; do not reimplement driver stack |
| RGB | unresolved | no selected maintained path | optional follow-up; Tier-3 RE if necessary |
| Frost Bay | BlueZ + unknown protocol | `RESEARCH_PENDING` | project research/backend later |
| Mini SSD presence | PCIe/NVMe | `READ_ONLY` classifier | diagnostics/UI |
| Mini SSD reliability | research qualification | `NOT_QUALIFIED` | do not claim healthy pre-research |

## Contention

Only one component should actively own a mutable setting where possible. If another daemon manages a setting, Super X Helper should integrate, explicitly take ownership with user intent, or stay read-only.

## Backend rule

Good:

```text
UI capability ID
    ↓
service validates capability + authorization + range
    ↓
resolved backend operation
    ↓
read observed state
```

Bad:

```text
UI → arbitrary path / shell string / raw EC write
```

## Fan-specific note

The code no longer claims automatic restoration to firmware fan mode on shutdown. That behavior is a future acceptance criterion, not a current fact.
