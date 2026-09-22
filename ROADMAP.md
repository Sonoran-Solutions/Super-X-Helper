# Super X Helper — Roadmap and Task List

**Last research refresh:** 2026-09-22

The roadmap is integration-first and reuse-first. Super X Helper remains an Ubuntu-native GTK daily-driver application; it should not duplicate mature open-source hardware-control work merely because that work lives in a different UI or distro ecosystem.

## Current strategy

The current state is:

    trustworthy hardware/capability foundation        COMPLETE
                     ↓
    GTK4/libadwaita read-only application shell       COMPLETE
                     ↓
    live read-only Super X integration pass           COMPLETE
                     ↓
    upstream reuse audit + root write validation      NEXT
                     ↓
    PRE-ASTRA daily-driver checkpoint
                     ↓
    Frost Bay local validation/adaptation
    Mini SSD fault isolation
                     ↓
    production integration and packaging

Two discoveries materially change the old plan:

1. **Loadout is now a serious reference implementation for handheld fan/TDP/battery/RGB control.** Before implementing production fan curves, persistence, locking, hwmon scanning, watchdogs, or TDP plumbing from scratch, audit Loadout and deliberately reuse/adapt the parts that fit our capability/service contract.
2. **Frost Bay is no longer an undocumented-protocol problem.** A public verified protocol reference and two HHD implementations now exist. Our task is to reproduce that evidence on the Super X, validate BlueZ transport reliability, and adapt it safely—not repeat protocol archaeology from zero.

Mini SSD disappearance/reliability remains unresolved and is still the primary premium-model research candidate.

## Evidence state

- GTK shell/read-only pages exist.
- Fresh live read-only baseline was captured on 2026-09-07; suite was 45 passing tests at that handoff.
- Installed Ubuntu kernel 7.0.0-30-generic contains oxpec but lacks the Super X DMI quirk; no live oxp_ec hwmon was available.
- Upstream Linux added a Super X oxpec mapping after that kernel. A kernel/backport containing the quirk must be validated locally before fan writes.
- Loadout has generic hwmon fan control, mode persistence, operation serialization, bounded writes, safety-floor/watchdog logic, and OneXPlayer capability detection. Super X is not on Loadout's published tested-device list.
- Public Frost Bay work documents the FFE0/FFE1 control path, 64-byte state, BlueZ D-Bus access, telemetry/control semantics, and chunked writes. Local Super X transport/health behavior is not yet validated.
- No credible public root-cause or firmware fix has been established for the BIWIN Mini SSD disappearance problem.

See docs/LIVE_INTEGRATION_HANDOFF.md, docs/UPSTREAM_OWNERSHIP.md, docs/FROST_BAY.md, and docs/MINI_SSD.md.

## GitHub issue map

Use [#21 — Roadmap tracker](https://github.com/Sonoran-Solutions/Super-X-Helper/issues/21) as the GitHub-level progress view.

| Roadmap area | Issue |
|---|---|
| `SX-UPSTREAM-001` Loadout audit | [#7](https://github.com/Sonoran-Solutions/Super-X-Helper/issues/7) |
| `SX-CORE-002` oxpec/oxp_ec live validation | [#8](https://github.com/Sonoran-Solutions/Super-X-Helper/issues/8) |
| `SX-CORE-003` ordinary write qualification | [#9](https://github.com/Sonoran-Solutions/Super-X-Helper/issues/9) |
| `SX-CORE-004` production TDP backend | [#10](https://github.com/Sonoran-Solutions/Super-X-Helper/issues/10) |
| `SX-CORE-005` D-Bus/polkit production boundary | [#11](https://github.com/Sonoran-Solutions/Super-X-Helper/issues/11) |
| `SX-UI-003/005/006` Performance/Display/Power activation | [#12](https://github.com/Sonoran-Solutions/Super-X-Helper/issues/12) |
| `SX-UI-004` internal fan controls/curves | [#13](https://github.com/Sonoran-Solutions/Super-X-Helper/issues/13) |
| `SX-UI-007/008` controller/gyro/RGB integration audit | [#14](https://github.com/Sonoran-Solutions/Super-X-Helper/issues/14) |
| `SX-UI-009` transactional profiles | [#15](https://github.com/Sonoran-Solutions/Super-X-Helper/issues/15) |
| `SX-UI-010` quick access | [#16](https://github.com/Sonoran-Solutions/Super-X-Helper/issues/16) |
| Frost Bay validation (`SX-FB-002..006`) | [#4](https://github.com/Sonoran-Solutions/Super-X-Helper/issues/4) |
| Frost Bay production + liquid safety (`SX-FB-007`, `SX-INTEGRATE-001/002`) | [#17](https://github.com/Sonoran-Solutions/Super-X-Helper/issues/17) |
| Mini SSD root cause (`SX-SSD-001..004`) | [#5](https://github.com/Sonoran-Solutions/Super-X-Helper/issues/5) |
| Mini SSD qualification/health (`SX-SSD-005/006`, `SX-INTEGRATE-003`) | [#18](https://github.com/Sonoran-Solutions/Super-X-Helper/issues/18) |
| `SX-HARD-001/002` hardware regression + recovery | [#19](https://github.com/Sonoran-Solutions/Super-X-Helper/issues/19) |
| `SX-HARD-003/004/005` privilege/package/compatibility | [#20](https://github.com/Sonoran-Solutions/Super-X-Helper/issues/20) |

Legacy foundation issues [#1](https://github.com/Sonoran-Solutions/Super-X-Helper/issues/1), [#2](https://github.com/Sonoran-Solutions/Super-X-Helper/issues/2), and [#3](https://github.com/Sonoran-Solutions/Super-X-Helper/issues/3) predate the current roadmap refresh; their corresponding foundation work is now complete in the roadmap and can be reconciled/closed separately.

## Model guidance

- Tier 1: scaffolding, UI implementation, tests, docs, mechanical integration.
- Tier 2: Linux/backend integration, correctness review, live write validation, upstream adaptation.
- Tier 3: difficult debugging or targeted static/reverse engineering after maintained upstream work is exhausted.
- Tier 4: unresolved cross-layer hardware research.

**Core rule:** premium research should inherit the public and local evidence packet. Do not spend Tier-4 budget re-deriving an upstream implementation that can be audited first.

---

# Phase 0 — Trustworthy foundation

## SX-001 · Capture immutable hardware/software inventory — COMPLETE

Baseline and refreshed live snapshot exist.

## SX-002 · Inventory existing Linux controls — BASELINE COMPLETE

The inventory must now include Loadout as a reference implementation and the public Frost Bay/HHD work. Discovery still does not authorize writes.

## SX-003 · Read-only diagnostic collector — COMPLETE IN CODE

Collector covers DMI/kernel/module state, hwmon/sysfs telemetry, PCIe/NVMe discovery, Mini SSD presence classification, SMART/error fields, filtered kernel messages, passive BlueZ metadata, and identifier redaction.

## SX-004 · Tier-2 audit/hardening pass — COMPLETE

See docs/PHASE0_HANDOFF.md.

---

# Phase 1 — Daily-driver control center

## SX-CORE-001 · Application architecture — COMPLETE

Accepted architecture:

    GTK4/libadwaita UI
            ↓ ServiceClient
    system D-Bus + polkit
            ↓
    Python superx-helperd service facade
            ↓
    validated platform / storage / Frost Bay backends

The capability contract remains authoritative. Upstream reuse must fit this contract rather than bypass it.

## SX-UI-001 · GTK shell + capability-driven read-only pages — COMPLETE

The shell, navigation, Dashboard, and read-only page skeletons are already implemented. Do not assign another agent to rebuild them.

## SX-LIVE-001 · First live-machine integration pass — COMPLETE

Fresh baseline captured and UI/service boundary corrected. See docs/LIVE_INTEGRATION_HANDOFF.md.

## SX-UPSTREAM-001 · Audit Loadout before production fan/TDP work — P0 / NEXT

Review [srsholmes/loadout](https://github.com/srsholmes/loadout), especially:

- plugins/fan-control/backend.ts
- plugins/fan-control/safety-floor.ts
- plugins/fan-control/lib/global-mode.ts
- fan-control tests around stale ticks, ownership restoration, watchdog behavior, write timeouts, and concurrency
- plugins/tdp-control/
- OneXPlayer capability detection and battery/RGB plugins where relevant

Answer explicitly:

- Which algorithms/design patterns should be adapted?
- Which assumptions are Gaming-Mode/SteamOS-specific and should not be imported?
- Which parts require attribution/license handling?
- Which parts are safe to reproduce as design patterns versus direct code reuse?
- Which Super X behavior still needs local validation?

**Do not implement a second fan-curve engine before this audit.**

## SX-CORE-002 · Validate the Super X oxpec/oxp_ec path under root — P0

1. Boot a kernel or backport containing the Super X oxpec quirk.
2. Confirm oxp_ec hwmon identity and fan1_input / pwm1 / pwm1_enable behavior.
3. Record automatic/manual semantics from the live device.
4. Validate recovery back to firmware/EC ownership.
5. Only then authorize fan writes through the service contract.

Loadout's fan backend is a reference for failure handling, not proof that this Super X path works unchanged.

## SX-CORE-003 · Validate ordinary root-owned writes — P0

Perform one reversible capability at a time with before/read-back/restore evidence:

1. EPP
2. CPU boost
3. brightness
4. internal fan after SX-CORE-002

No power increase should be paired with first-time fan validation.

## SX-CORE-004 · Select production APU/TDP mechanism — P1

Audit Loadout's TDP strategy and current Linux/HHD options before selecting a backend. Preserve Super X Helper's own capability and safety policy. Do not couple Frost Bay detection directly into a legacy TDP backend.

## SX-CORE-005 · D-Bus/polkit production boundary — P1

Install only after at least one write capability has passed local validation.

## SX-UI-002 · Dashboard polish — P1

Current read-only Dashboard exists. Continue from it; do not rebuild the shell.

## SX-UI-003 · Performance page writes — P1

Activate only production-qualified EPP/boost/TDP capabilities.

## SX-UI-004 · Cooling page writes — P1

Use locally validated oxp_ec behavior and audited safety/recovery patterns. Custom curves require tested ownership restoration, bounded writes, stale-loop protection, and a thermal failsafe.

## SX-UI-005 · Display writes — P1

Prefer compositor/session-owned interfaces where practical. Validate brightness requested-vs-observed behavior before enabling it.

## SX-UI-006 · Power/Battery — P1

Telemetry exists. Charge limit/bypass remains unavailable until a local interface is proven. Audit upstream OneXPlayer implementations before adding custom EC behavior.

## SX-UI-007 · Controller/vibration/gyro — P2

Prefer HHD/InputPlumber/Steam. Do not build another controller stack.

## SX-UI-008 · RGB — P2

Audit maintained Loadout/HHD/OpenRGB paths before proprietary reverse engineering.

## SX-UI-009 · Declarative profiles — P1

Profiles remain high-level policy. Transactional apply/rollback is required before multi-setting writes are production-ready.

## SX-UI-010 · Quick-access panel/hotkey — P1

Compact second GTK window using the same ServiceClient; reuse maintained input ownership where possible.

### PRE-ASTRA gate

- [x] trustworthy diagnostic/capability foundation
- [x] refreshed live diagnostic snapshot
- [x] GTK application shell and read-only pages
- [ ] Loadout fan/TDP upstream audit completed
- [ ] CPU/performance writes locally validated
- [ ] internal fan path locally validated with ownership recovery
- [ ] display writes enabled only where proven
- [ ] battery telemetry and any supported controls
- [ ] declarative profiles
- [ ] quick-access workflow
- [x] Mini SSD presence telemetry with NOT_QUALIFIED warning
- [x] Frost Bay represented as RESEARCH_PENDING without pretending local validation
- [ ] unresolved ordinary features classified/documented

---

# Phase 2 — Frost Bay validation and integration

The old from-scratch reverse-engineering plan is superseded.

Public reference:
- [tbitu/onexplayer-frostbay-bluetooth](https://github.com/tbitu/onexplayer-frostbay-bluetooth)
- [hhd-dev/hhd PR #321](https://github.com/hhd-dev/hhd/pull/321)
- [hhd-dev/hhd PR #336](https://github.com/hhd-dev/hhd/pull/336)

## SX-FB-001 · Public protocol intake — COMPLETE

Public work already establishes the core FFE0/FFE1 protocol model and Linux BlueZ execution path. Treat it as high-confidence external evidence, not local confirmation.

## SX-FB-002 · Reproduce BlueZ transport on the Super X — P0 / NEXT FROST BAY TASK

On the actual Super X:

- identify the local Frost Bay device;
- confirm Connected + ServicesResolved;
- confirm FFE0/FFE1 visibility;
- read state through BlueZ D-Bus;
- determine whether the built-in Bluetooth controller exposes the full GATT tree reliably;
- record any HID side effects.

If the built-in adapter fails but an external adapter works, document that as a transport limitation rather than inventing a protocol problem.

## SX-FB-003 · Validate public field semantics locally — P0

Independently confirm the small set of fields required for UI/health: requested mode, fan/pump command, runtime activity, water temperatures, flow telemetry, and freshness.

Do not re-run static OneXConsole archaeology unless local evidence contradicts the public protocol reference.

## SX-FB-004 · Read-only Frost Bay backend — P1

Implement through the existing capability/service contract. BlueZ owns transport; the backend owns protocol parsing and freshness state.

## SX-FB-005 · Minimum safe control reproduction — P1

Reproduce one published benign/reversible write with before/read-back/restore evidence. No blind writes and no maximum-power pairing.

## SX-FB-006 · State machine / disconnect handling — P1

Disconnected, stale, unknown, partial-GATT, or faulted never equals healthy.

## SX-FB-007 · Liquid-power safety gate — P1

Liquid-only power policy must consume validated cooler health from the Frost Bay backend. Keep dock detection separate from the selected TDP implementation.

### Superseded Frost Bay work — DO NOT REPEAT BY DEFAULT

- broad passive discovery as if UUIDs were unknown;
- full vendor protocol archaeology from scratch;
- Astra mission to discover basic FFE1 semantics;
- speculative BLE fuzzing or unknown characteristic writes.

Escalate only when the local Super X materially disagrees with the published evidence.

---

# Phase 3 — Mini SSD deep research

Issue #5 remains the primary unresolved hardware research mission.

No credible public breakthrough as of 2026-09-22 changes this plan.

## SX-SSD-001 · Refresh known-good baseline — P0

Use the hardened collector to capture current PCIe/NVMe/namespace/link/temp/SMART/kernel state.

## SX-SSD-002 · Reproduce disappearance systematically — P0 / RESEARCH

Run the bounded experimental matrix after cheaper models reduce logs where useful.

## SX-SSD-003 · Determine failure layer — P0 / RESEARCH

Discriminate physical/contact, slot power, link training, ASPM, NVMe controller/reset/firmware, thermals, I/O/filesystem, or defective hardware.

## SX-SSD-004 · Test minimum mitigation — P1 / RESEARCH

Change one evidence-backed variable at a time and require repeatability.

## SX-SSD-005 · Reliability qualification — P1

Only after root-cause/mitigation work, run repeated boot/suspend/idle/read/write/checksum/thermal qualification.

## SX-SSD-006 · Production health monitor — P2

Only then replace NOT_QUALIFIED with evidence-backed qualified/degraded/fault states.

---

# Phase 4 — Integrate validated discoveries

## SX-INTEGRATE-001 · Frost Bay production backend — P1

Activate the existing cooling UI only after local transport, field, freshness, and recovery validation.

## SX-INTEGRATE-002 · Liquid profile activation — P1

Enable only after cooler-health/fallback behavior and the independent TDP path are verified.

## SX-INTEGRATE-003 · Mini SSD qualified health states — P1

If the final answer is hardware/firmware unreliability, say so rather than manufacturing a software success state.

---

# Phase 5 — Hardening and packaging

- SX-HARD-001: opt-in hardware regression suite
- SX-HARD-002: safe startup/recovery
- SX-HARD-003: D-Bus/polkit privilege review
- SX-HARD-004: Ubuntu .deb packaging
- SX-HARD-005: compatibility/diagnostic report
- SX-HARD-006: broader ONEXPLAYER evaluation only after Super X is solid

---

# Next model handoff

**Recommended next engineering task:** SX-UPSTREAM-001 followed by root live validation.

The handoff should say:

> Audit Loadout's current fan-control and TDP implementations before adding production write logic to Super X Helper. Map reusable design patterns into our capability/service architecture, with special attention to generic hwmon discovery, pwm1_enable ownership, persisted global mode, serialized operations, stale curve ticks, bounded EC/sysfs writes, independent thermal watchdog behavior, and recovery to automatic control. Do not copy Steam/Gaming-Mode assumptions or enable writes. Produce a concrete adaptation plan, then validate the Super X oxpec/oxp_ec path under root on a kernel containing the Super X quirk.

For Frost Bay, the next task is no longer protocol discovery. It is local BlueZ reproduction of the published FFE0/FFE1 path.
