# Super X Helper — Roadmap and Task List

This roadmap is **integration-first, research-when-necessary**. The immediate product goal is to make the Ubuntu Super X a comfortable daily driver with one Linux-native control center for every feature that can already be implemented safely. Frost Bay protocol work and Mini SSD root-cause work remain separate deep-research tracks and should not block the ordinary control-center experience.

## Current strategy

```text
trustworthy hardware baseline
        ↓
harden capability/diagnostic layer
        ↓
build Linux OneXConsole-style daily-driver UI
        ↓
PRE-ASTRA CHECKPOINT
        ↓
Frost Bay deep research + Mini SSD fault isolation
        ↓
integrate confirmed discoveries into the finished app
```

The application should already contain UI/state placeholders for the two research tracks before they are solved:

- **Frost Bay:** `RESEARCH_PENDING` until protocol/health/control semantics are proven.
- **Mini SSD reliability:** basic presence/temperature/PCIe/NVMe telemetry may be shown, but reliability remains `NOT_QUALIFIED` until the fault-isolation and qualification work passes.

Priority meanings:

- **P0** — required for the current milestone.
- **P1** — core product capability.
- **P2** — quality-of-life / hardening.
- **RESEARCH** — evidence-gathering task whose result may change implementation.

## Model guidance

Use the Sonoran model ladder rather than assigning premium models by project prestige:

- **Tier 1 — Gemini 3.8 Flash / DeepSeek V4 Flash:** inventories, scaffolding, UI implementation, tests, docs, mechanical integration.
- **Tier 2 — GPT-5.6 Terra Medium:** normal serious engineering, cross-component correctness, backend/system integration, review of Tier-1 output.
- **Tier 3 — DeepSeek V4 Pro High:** hard debugging, difficult architecture, static reverse engineering, second opinion after serious Tier-2 attempts.
- **Tier 4 — GPT-6 Astra Medium/High:** undocumented protocols, experimental hardware debugging, cross-layer root-cause work, autonomous hypothesis → experiment loops.

**Core rule:** Astra should usually receive evidence produced by cheaper models rather than being asked to gather all of the evidence itself.

---

# Phase 0 — Trustworthy foundation

Gemini 3.8 Flash completed a useful first pass over SX-001/SX-002 and scaffolded SX-003. Treat that work as **provisional evidence that now requires a bounded Tier-2 verification pass**, not as blanket proof that every documented control has been exercised on hardware.

## SX-001 · Capture immutable hardware/software inventory — P0 / RESEARCH

Record:

- exact Super X SKU / liquid-cooled edition identity;
- DMI vendor/product/board strings;
- BIOS/UEFI version;
- Ubuntu release and kernel version;
- CPU/GPU identity;
- Bluetooth adapter and driver;
- internal SSD identity;
- Mini SSD PCIe/NVMe identity when detected;
- currently loaded ONEXPLAYER/platform modules;
- Frost Bay advertised identity later during passive discovery if it is not yet known.

**Current state:** substantially captured in `docs/local-hardware-baseline.md`; Frost Bay local identity remains intentionally unresolved.

**Acceptance:** the development machine can be distinguished from another hardware/firmware revision without publishing unnecessary unique identifiers or secrets.

## SX-002 · Inventory existing Linux controls — P0 / RESEARCH

Identify useful controls already exposed by maintained Linux interfaces:

- `oxpec`/hwmon fan controls and telemetry;
- turbo/performance toggles;
- battery charge controls where actually exposed;
- CPU/APU power interfaces and RyzenAdj only where required;
- display resolution/refresh/VRR interfaces;
- RGB support through existing maintained projects where possible;
- controller/gyro/device support through HHD/InputPlumber/Steam or alternatives.

Classify each capability as:

- **CONFIRMED_LOCAL** — exercised/observed directly on this Super X;
- **SUPPORTED_UNVERIFIED** — interface/source evidence exists, but this exact write/read path has not yet been exercised;
- **READ_ONLY** — trustworthy telemetry exists but control is not validated;
- **RESEARCH_PENDING** — requires additional protocol/hardware work;
- **UNAVAILABLE** — not currently exposed by the selected Linux stack;
- **ERROR** — expected capability exists but is currently failing.

**Acceptance:** implementation does not duplicate a maintained upstream feature without a specific reason and does not call an unexercised hardware write "verified".

## SX-003 · Finish read-only diagnostic collector — P0

The collector must export useful evidence while remaining unable to modify hardware state.

Finish/harden:

- DMI/kernel/module state;
- relevant hwmon/sysfs state;
- stable PCIe/NVMe controller + namespace resolution;
- Mini SSD PCIe/NVMe presence classification;
- SMART/health/error telemetry where safely readable;
- relevant filtered kernel messages;
- Bluetooth adapter/device/service inventory without secrets;
- privacy redaction for serial numbers, Bluetooth addresses, credentials, usernames, or unrelated personal data by default.

**Acceptance:** running the default collector cannot modify fan, power, BLE, EC, filesystem, or storage state and produces a trustworthy bundle for later research sessions.

## SX-004 · Tier-2 audit/hardening pass — P0

Review the Gemini-generated foundation before building the production UI.

At minimum:

- correct overconfident `complete` / `verified` documentation claims;
- fix NVMe namespace detection and state classification gaps;
- verify diagnostics redaction;
- make requested-vs-observed write verification real rather than cosmetic;
- ensure a failed fan-mode transition prevents a subsequent duty write;
- do not claim automatic fan rollback unless implemented and tested;
- keep capability discovery separate from permission/control authorization;
- mark unvalidated write paths experimental or disabled until hardware verification exists.

**Recommended model:** **GPT-5.6 Terra Medium**.

**Exit criteria for Phase 0:** the repo contains a trustworthy read-only evidence layer and a capability model that clearly separates observed facts from merely available/provisional control paths.

---

# Phase 1 — Pre-Astra daily-driver control center

**Goal:** reach a usable Linux-native OneXConsole replacement for every ordinary feature that can be implemented safely **before** spending Astra on Frost Bay or the Mini SSD fault investigation.

See [`docs/PRE_ASTRA_CHECKPOINT.md`](docs/PRE_ASTRA_CHECKPOINT.md).

## SX-CORE-001 · Lock the pre-Astra application architecture — P0

Choose the practical stack using the code and interfaces that now exist. Do not rewrite working Python scaffolding merely for architectural fashion.

Decide and document:

- UI toolkit;
- unprivileged UI ↔ privileged service/daemon boundary;
- DBus/polkit or equivalent local IPC/authorization;
- capability/state schema;
- event/telemetry update model;
- configuration/profile storage;
- packaging strategy for Ubuntu.

**Acceptance:** an ADR explains the choice and how existing `superx_helper` code migrates or remains in place.

**Recommended model:** Terra Medium. Escalate to V4 Pro only if a real integration problem warrants it.

## SX-CORE-002 · Harden platform service/backend — P0

Provide a narrow typed backend for confirmed Linux interfaces.

Initial scope:

- CPU boost/EPP and selected power controls once verified;
- internal fan telemetry/control once `oxpec` is loaded and the exact hwmon behavior is validated;
- battery telemetry and charge controls only where actually supported;
- display brightness and selected display controls;
- thermals/power telemetry;
- Mini SSD basic read-only state/temperature/link data;
- diagnostics export.

No arbitrary sysfs path or shell command may come from UI input.

## SX-CORE-003 · CLI/service status surface — P1

Provide a stable troubleshooting API/CLI before the GUI depends on it, e.g.:

```text
superxctl status
superxctl performance status
superxctl fan status
superxctl display status
superxctl storage mini-ssd status
superxctl diagnostics export
```

Write commands become available only for hardware paths that pass the research-to-production gate.

## SX-UI-001 · Application shell + capability-driven UI — P0

Build a polished Linux-native control center whose widgets derive from backend capability state rather than hard-coded device assumptions.

Every feature can render states such as:

```text
AVAILABLE_READ_WRITE
READ_ONLY
SUPPORTED_UNVERIFIED
RESEARCH_PENDING
UNAVAILABLE
ERROR
```

Frost Bay and Mini SSD reliability must be visible without pretending they are solved.

## SX-UI-002 · Dashboard — P1

Show at-a-glance:

- active profile;
- CPU/GPU temperature and useful power telemetry;
- internal fan state;
- battery state;
- display mode;
- Frost Bay status (`RESEARCH_PENDING` pre-Astra);
- Mini SSD presence/temperature plus `NOT_QUALIFIED` reliability state;
- meaningful backend warnings/errors.

## SX-UI-003 · Performance page — P1

Expose confirmed controls only:

- CPU boost;
- EPP/performance preference;
- package/APU power target if a validated control method exists;
- observed power/thermal state;
- profile selection.

Reserve a disabled **Liquid Performance** profile/state for later Frost Bay integration. It must not be selectable until a positive, fresh, validated cooler-health signal exists.

## SX-UI-004 · Internal cooling page — P1

After `oxpec` behavior is validated on this hardware:

- automatic/manual mode;
- current fan duty/RPM where exposed;
- safe presets;
- custom temperature→fan curve if the backend can enforce it safely;
- rollback/recovery behavior.

Frost Bay appears in this page as a separate disabled/research-pending section until Phase 2 completes.

## SX-UI-005 · Display page — P1

Where supported by the active Ubuntu compositor/session:

- brightness;
- resolution selection;
- refresh-rate selection;
- VRR status/toggle when a reliable interface exists;
- current connected display state.

Do not fight the compositor for ownership.

## SX-UI-006 · Power / battery page — P1

Show:

- charge state/percentage/health telemetry;
- performance preference/boost relationship where useful;
- charge limit/bypass charging only if a trustworthy Linux control path is proven;
- unavailable controls visibly labeled rather than guessed.

## SX-UI-007 · Existing controller / vibration / gyro integration — P2

Prefer integration with HHD/InputPlumber/Steam or another maintained owner rather than implementing a competing controller stack.

Expose controls in Super X Helper only when a stable integration API exists.

## SX-UI-008 · RGB integration — P2

First search for maintained Linux support. If a normal integration exists, use it. If the remaining gap becomes proprietary HID/USB reverse engineering, route static analysis to **DeepSeek V4 Pro High** before considering Tier 4.

RGB is desirable but does not block the pre-Astra gate if the only route is a substantial independent reverse-engineering project.

## SX-UI-009 · Declarative profiles — P1

Support named transactional profiles such as:

- Quiet;
- Balanced;
- Performance;
- Custom;
- Liquid Performance (defined but unavailable until Frost Bay is verified).

Profiles contain high-level policy, not raw paths, commands, registers, or BLE packets. Failed multi-setting application must roll back cleanly where practical.

## SX-UI-010 · Quick-access panel / hotkey — P1

Provide a compact in-game panel or quick-access window for high-frequency controls:

- profile;
- power target where supported;
- fan mode;
- brightness;
- refresh rate;
- key telemetry.

Integrate with an existing Super X button/input stack where possible rather than building a new driver.

## SX-UI-011 · Game-aware profile association — P2

Optional after the normal profile engine works. Associate detected processes/games with user-selected profiles without turning Super X Helper into another game launcher.

## PRE-ASTRA GATE

Do **not** begin expensive deep research merely because Phase 1 looks fun. The checkpoint passes when the application is useful as a daily driver without Frost Bay and without trusting the Mini SSD.

Required:

- [ ] trustworthy diagnostics/capability layer;
- [ ] polished application shell/dashboard;
- [ ] confirmed CPU/performance controls available from UI;
- [ ] confirmed internal fan controls available from UI;
- [ ] display/brightness controls available where Linux exposes them;
- [ ] battery telemetry and supported controls;
- [ ] declarative profiles;
- [ ] quick-access workflow;
- [ ] Mini SSD basic presence/temp/link telemetry shown with `NOT_QUALIFIED` warning;
- [ ] Frost Bay visible as `RESEARCH_PENDING`, with no guessed control path;
- [ ] unresolved ordinary features documented as either a normal follow-up or a separate research problem.

At this point the product should already replace the majority of the Windows OneXConsole functionality the owner actually uses.

---

# Phase 2 — Frost Bay deep research

Issue #4 remains the main research mission.

## SX-FB-001 · Passive Frost Bay Bluetooth discovery — P0 / RESEARCH

Use a cheaper reconnaissance model first to capture:

- exact local Bluetooth identity/address type without publishing unnecessary identifiers;
- advertisements/service UUIDs;
- GATT services/characteristics/descriptors/properties;
- safe reads/notifications where available.

**Recommended model:** Gemini 3.8 Flash Medium for passive collection; Terra reviews the evidence.

## SX-FB-002 · Static OneXConsole protocol archaeology — P0 / RESEARCH

Inspect publicly distributed OneXConsole binaries/resources for Frost Bay-specific names, UUIDs, packet structures, telemetry labels, command identifiers, reconnect behavior and safety/range checks.

**Recommended model:** **DeepSeek V4 Pro High** first.

## SX-FB-003 · Astra protocol mission — P0 / RESEARCH

Hand Astra the curated evidence packet from passive GATT discovery + static archaeology. Its job is to resolve the remaining undocumented semantics through the smallest safe experiments, not to rediscover the baseline.

**Recommended model:** **GPT-6 Astra High**.

## SX-FB-004 · Linux read-only client — P1

Implement discovery, identity validation, connection lifecycle, notifications and confirmed telemetry decoding.

**Recommended model:** Terra Medium once protocol facts are known.

## SX-FB-005 · Minimum safe Linux control POC — P1

Perform the first benign reversible control only after identity, characteristic, encoding, safe range, expected effect and rollback are confirmed.

**Recommended model:** Astra High for the first unresolved hardware experiment; Terra for implementation afterward.

## SX-FB-006 · Frost Bay state machine / fault handling — P1

Model disconnected, connecting, connected/unknown, healthy, degraded/fault, and stale telemetry states. Stale or missing telemetry is never equivalent to healthy.

## SX-FB-007 · Liquid-power safety gate — P1

Liquid-only profiles require a positive fresh cooler-health signal and a verified fallback policy on disconnect/fault.

---

# Phase 3 — Mini SSD deep research

Issue #5 remains the main research mission.

## SX-SSD-001 · Finish known-good baseline/state classifier — P0

The pre-Astra collector should already provide read-only PCIe/NVMe identity, namespace, link, temperature and health evidence. Confirm the baseline is sufficient for before/after comparison.

## SX-SSD-002 · Reproduce disappearance systematically — P0 / RESEARCH

Run a controlled matrix across cold boot, warm reboot, idle, suspend/resume, safe reads, explicitly disposable writes when authorized, post-load idle, and thermal rise/cooldown.

**Recommended model:** Astra High for the experimental fault-isolation loop; Gemini Flash may reduce/organize large diagnostic logs first.

## SX-SSD-003 · Determine failure layer — P0 / RESEARCH

Discriminate among:

- physical seating/contact;
- slot power;
- PCIe link training;
- ASPM/power management;
- NVMe controller power/reset/firmware;
- thermals;
- I/O/filesystem;
- defective hardware.

Do not select a permanent workaround until the failure layer is demonstrated.

## SX-SSD-004 · Test minimum mitigation — P1 / RESEARCH

Change one evidence-backed variable at a time and demand repeatability.

## SX-SSD-005 · Reliability qualification — P1

Only after mitigation/root-cause work, run the defined repeated boot/suspend/idle/read/write/checksum/thermal qualification suite.

## SX-SSD-006 · Production storage health monitor — P2

Upgrade the pre-Astra basic storage card to show qualified/degraded/fault states and bounded recent error history.

---

# Phase 4 — Integrate research discoveries

## SX-INTEGRATE-001 · Frost Bay production backend — P1

Move only confirmed protocol semantics into typed production code/fixtures and activate the existing cooling UI.

## SX-INTEGRATE-002 · Liquid profile activation — P1

Enable Liquid Performance only after cooler-health/fault behavior and safe fallback policy are verified.

## SX-INTEGRATE-003 · Mini SSD qualified health states — P1

Replace `NOT_QUALIFIED` with the evidence-backed health/qualification model. If the result is "hardware/firmware unreliable," the UI should say so rather than invent a software success state.

---

# Phase 5 — Hardening and packaging

## SX-HARD-001 · Hardware regression suite — P1

Opt-in tests for supported control paths.

## SX-HARD-002 · Safe startup/recovery — P1

Daemon crash/restart must not leave unsafe assumptions about fan, Frost Bay or power state.

## SX-HARD-003 · Permissions/polkit review — P1

Minimize root capability.

## SX-HARD-004 · Ubuntu packaging — P1

Package daemon, CLI, UI, service files and permissions cleanly.

## SX-HARD-005 · Compatibility report — P2

Expose kernel/version/interfaces detected so bug reports are actionable.

## SX-HARD-006 · Broader ONEXPLAYER evaluation — P2

Only after the Super X works reliably, identify reusable architecture for related devices without leaking model-specific hacks into shared code.

---

# First Astra missions

Astra should not build the ordinary application.

**Frost Bay mission:**

> Given the confirmed local GATT map, passive notification captures, static OneXConsole findings, and existing Super X Helper backend/UI contracts, resolve the remaining Frost Bay protocol semantics through the minimum safe evidence-producing experiments and prove a read-only telemetry path plus the smallest reversible control path.

**Mini SSD mission:**

> Given the trusted diagnostic collector and known-good Mini SSD baseline, execute the bounded fault-isolation experiment until disappearance/reliability failures are localized to PCIe enumeration, NVMe controller/namespace, I/O, thermal, power-management, firmware, or physical behavior with evidence strong enough to justify exactly one minimum mitigation experiment.

Once either research problem is solved, step back down to Terra/Flash for normal product integration.