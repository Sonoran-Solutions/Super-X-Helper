# Super X Helper — Upstream Controls & Ownership Reference

**Last reviewed:** 2026-09-22

**Status:** upstream ownership/reuse baseline. Nothing in this document implicitly authorizes a hardware write on the local Super X.

## Ownership policy

1. Prefer stable upstream kernel/sysfs/hwmon interfaces.
2. Prefer maintained open-source implementations over re-inventing hardware-control machinery.
3. Keep Super X Helper's own capability/service/safety contract even when adapting upstream work.
4. Integrate with maintained userspace owners such as HHD/InputPlumber instead of duplicating controller stacks.
5. Discovery and public implementation evidence are not local write authorization.

## Current matrix

| Subsystem | Primary owner/reference | Current local state | Super X Helper role |
|---|---|---|---|
| Internal fan | Linux oxpec / oxp_ec hwmon; Loadout fan-control as userspace reference | SUPPORTED_UNVERIFIED; current captured kernel lacks Super X DMI quirk | validate local hwmon, then adapt proven safety/ownership patterns |
| CPU boost | Linux cpufreq | read observed; write unverified | capability adapter after live validation |
| EPP | amd-pstate-epp | read observed; write unverified | capability adapter after live validation |
| APU/TDP | Linux/firmware path to be selected; Loadout TDP + HHD as references | no production-selected local backend | audit first, then choose one evidence-backed adapter/range |
| Battery telemetry | power_supply | READ_ONLY | display telemetry |
| Charge limit/bypass | oxpec may expose support on relevant layouts; Loadout battery plugin is a reference | not live-validated | do not guess; validate local interface first |
| Display | compositor/DRM/amdgpu | telemetry observed | integrate without fighting desktop ownership |
| Controller/gyro/vibration | HHD/InputPlumber/Steam/kernel input | maintained external owners | integrate; do not reimplement |
| RGB | Loadout/OpenRGB/HHD are references | not locally selected | audit maintained paths before RE |
| Frost Bay | BlueZ transport + public FFE1 protocol reference + HHD implementations | RESEARCH_PENDING locally | reproduce/validate public protocol, then adapt |
| Mini SSD presence | PCIe/NVMe | READ_ONLY classifier | diagnostics/UI |
| Mini SSD reliability | local research qualification | NOT_QUALIFIED | do not claim healthy pre-research |

## Loadout: mandatory audit before fan/TDP reinvention

Reference: [srsholmes/loadout](https://github.com/srsholmes/loadout)

Loadout is not a drop-in replacement for Super X Helper. It targets Linux gaming handhelds with a root-backed plugin service and Gaming Mode/desktop UI, while this project is Ubuntu-native GTK with a typed capability contract. It is, however, mature enough that ignoring it would waste engineering effort.

### Relevant proven design work

Fan-control code currently includes:

- generic /sys/class/hwmon scanning rather than fixed hwmonN paths;
- PWM and RPM-target strategies;
- handling for pwmN_enable ownership;
- persisted global mode/profile intent;
- serialization of user/profile operations;
- stale curve-tick/generation handling;
- bounded sysfs writes so a wedged EC cannot hold the operation lock forever;
- an independent thermal safety watchdog that can take over when the normal curve writer stalls;
- restoration of automatic/firmware ownership on unload;
- live-vs-commanded duty distinctions;
- tests for concurrency and safety regressions.

Useful entry points include:

- plugins/fan-control/backend.ts
- plugins/fan-control/safety-floor.ts
- plugins/fan-control/lib/global-mode.ts
- plugins/fan-control/backend.test.ts

Loadout's August 28, 2026 OneXPlayer change moved its device plugin away from an Apex-only hard gate toward per-feature capability detection. That is directionally aligned with Super X Helper's capability model, but does not establish Super X compatibility.

### TDP/battery/RGB

Loadout also has:

- a TDP plugin with RyzenAdj and device-capability logic;
- battery charge/bypass handling including awkward EC/sysfs behavior;
- RGB support across OpenRGB/sysfs/OneXPlayer paths.

Audit these before adding custom Super X-specific code.

### Adoption rule

Do not copy an implementation mechanically.

For every reused idea, document:

- upstream source and commit/area reviewed;
- behavioral invariant being adopted;
- assumptions that do not apply on Ubuntu/Super X;
- local evidence required before enabling it;
- attribution/license obligations if source code is reused.

Design patterns are preferred over wholesale code transplant when our architecture differs.

## Frost Bay: public protocol is now upstream evidence

Primary protocol reference:

- [tbitu/onexplayer-frostbay-bluetooth](https://github.com/tbitu/onexplayer-frostbay-bluetooth)

Active HHD implementation references:

- [hhd-dev/hhd PR #321 — Add Frostbay cooling plugin](https://github.com/hhd-dev/hhd/pull/321)
- [hhd-dev/hhd PR #336 — CoolingDockPlugin](https://github.com/hhd-dev/hhd/pull/336)

The public reference documents a normal BlueZ/GATT model centered on service FFE0 and characteristic FFE1, direct D-Bus ReadValue/WriteValue once Connected + ServicesResolved is true, a 64-byte state value, and known telemetry/control semantics.

This changes ownership of the research problem:

- **Do not** spend a new research pass discovering basic UUIDs/mode bytes from scratch.
- **Do** independently reproduce the published behavior on the actual Super X/Frost Bay.
- **Do** validate the built-in Bluetooth adapter; public work found controller/BlueZ-specific failures on an Apex path and success with an external adapter.
- **Do** keep local freshness/health/fault semantics inside Super X Helper's contract.

PR #336 also demonstrates why power policy remains ours: HHD review explicitly pushed dock behavior and TDP changes toward separate concerns. Super X Helper should consume validated cooler health from the Frost Bay backend rather than embed dock detection inside an unrelated legacy TDP path.

## Kernel oxpec ownership

The development machine's captured Ubuntu kernel includes oxpec but lacks the Super X DMI quirk. Upstream later added Super X support mapping to an existing OneXPlayer layout.

Therefore:

- kernel/hwmon owns the internal fan interface once the quirk is present;
- Super X Helper should not bypass that with undocumented raw EC writes;
- Loadout's fan logic is useful above that interface;
- local oxp_ec semantics still must be validated before can_write is enabled.

## Contention

Only one component should actively own a mutable setting where possible.

For fans in particular:

- automatic/firmware ownership must be recoverable;
- a profile/curve writer and a safety writer must not race blindly;
- stale queued work must not overwrite a newer user mode;
- a wedged hardware write must not disable the thermal failsafe.

These are acceptance criteria now, not future nice-to-haves.

## Backend rule

Good:

    UI capability ID
        ↓
    service validates capability + authorization + range
        ↓
    resolved backend operation
        ↓
    read observed state / verify / recover

Bad:

    UI → arbitrary path / shell string / raw EC or BLE bytes

## Repeat-work guard

Before starting work in any of these areas, search this document and the linked upstream projects:

- fan curves / PWM / hwmon
- TDP / RyzenAdj
- OneXPlayer capability detection
- battery charge/bypass
- RGB
- Frost Bay BLE

If maintained upstream code already solves the generic problem, the task becomes **audit + adapt + locally validate**, not **invent from scratch**.
