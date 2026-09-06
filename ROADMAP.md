# Super X Helper — Roadmap and Task List

The roadmap is **integration-first, research-when-necessary**. The immediate product target is a comfortable Ubuntu daily driver with one Linux-native control center for ordinary Super X functions. Frost Bay protocol work and Mini SSD root-cause work remain separate research tracks and must not block the normal application.

## Current strategy

```text
trustworthy hardware baseline
        ↓
Phase-0 Tier-2 hardening                 ← COMPLETE IN CODE
        ↓
Linux OneXConsole-style daily-driver UI ← NEXT
        ↓
PRE-ASTRA CHECKPOINT
        ↓
Frost Bay deep research + Mini SSD fault isolation
        ↓
integrate confirmed discoveries
```

Pre-research product states are intentional:

- **Frost Bay:** `RESEARCH_PENDING` until protocol/health/control semantics are proven.
- **Mini SSD reliability:** `NOT_QUALIFIED` until the fault-isolation and reliability-qualification tracks pass.

## Model guidance

- **Tier 1 — Gemini 3.8 Flash / DeepSeek V4 Flash:** scaffolding, UI implementation, tests, docs, mechanical integration.
- **Tier 2 — GPT-5.6 Terra Medium/High:** serious engineering, backend/system integration, correctness review, live hardware validation.
- **Tier 3 — DeepSeek V4 Pro High:** hard debugging, difficult architecture, static reverse engineering.
- **Tier 4 — GPT-6 Astra Medium/High:** undocumented protocols, cross-layer hardware fault isolation, autonomous hypothesis → experiment loops.

**Core rule:** Astra should usually inherit evidence produced by cheaper models rather than spending premium budget collecting the baseline.

---

# Phase 0 — Trustworthy foundation

## SX-001 · Capture immutable hardware/software inventory — P0 / RESEARCH

**Status:** substantially complete from the original Gemini pass.

Captured baseline includes Super X identity/revision, BIOS, Ubuntu/kernel, APU/GPU, display, battery, Bluetooth adapter, internal NVMe, Mini SSD PCIe/NVMe identity and `oxpec` module presence.

Remaining identity work belongs to later passive Frost Bay discovery, not to the normal UI milestone.

## SX-002 · Inventory existing Linux controls — P0 / RESEARCH

**Status:** baseline complete; local write validation remains intentionally separate.

Capability state vocabulary:

- `CONFIRMED_LOCAL`
- `SUPPORTED_UNVERIFIED`
- `READ_ONLY`
- `RESEARCH_PENDING`
- `UNAVAILABLE`
- `ERROR`

A discovered writable file is **not** equivalent to a production-qualified write capability.

## SX-003 · Finish read-only diagnostic collector — P0

**Status:** Tier-2 code hardening complete; re-run on the Super X after pulling this change to refresh the live snapshot.

Collector now covers:

- DMI/kernel/module state;
- hwmon/sysfs telemetry;
- stable PCIe/NVMe controller + namespace discovery;
- Mini SSD `ABSENT` / `PCIE_ONLY` / `NVME_PRESENT` presence classification;
- SMART/error fields via read-only `nvme-cli` where available;
- filtered relevant kernel messages;
- passive cached BlueZ target-like device/service inventory without starting a scan;
- default redaction of SSD serials/Bluetooth addresses;
- explicit identifier opt-in only when needed locally.

The collector must never label the Mini SSD `HEALTHY` from enumeration/SMART alone.

## SX-004 · Tier-2 audit/hardening pass — P0

**Status: COMPLETE (2026-09-06).**

Completed:

- [x] corrected optimistic verification assumptions;
- [x] fixed NVMe namespace discovery;
- [x] made Mini SSD presence classification require the correct layer evidence;
- [x] added default identifier redaction;
- [x] added read-only SMART/kernel telemetry paths;
- [x] separated discovery from write authorization;
- [x] made all writes fail closed by default;
- [x] made requested-vs-observed verification real;
- [x] stopped fan duty writes when manual-mode transition fails;
- [x] removed automatic-rollback claims until that behavior exists;
- [x] added typed capability/safety contract;
- [x] added Frost Bay `RESEARCH_PENDING` and Mini SSD `NOT_QUALIFIED` states;
- [x] expanded local unit suite to 22 passing tests.

See `docs/PHASE0_HANDOFF.md`.

### Phase-0 exit status

**Code gate passed.** Before enabling any real writes, re-run diagnostics and perform explicit live validation on the actual Super X.

---

# Phase 1 — Pre-Astra daily-driver control center

See:

- `docs/PRE_ASTRA_CHECKPOINT.md`
- `docs/UI_CONTRACT.md`
- `docs/adr/0001-python-gtk-dbus-architecture.md`

## SX-CORE-001 · Lock pre-Astra application architecture — P0

**Status: COMPLETE.**

Decision:

```text
GTK4/libadwaita UI (PyGObject, unprivileged)
        ↓ ServiceClient
system D-Bus + polkit
        ↓
Python superx-helperd service facade
        ↓
platform / storage / future Frost Bay backends
```

Additional decisions:

- keep the existing Python core for v0.1;
- no Rust rewrite without measured need;
- versioned capability records are the UI source of truth;
- daemon owns hardware polling and privileged writes;
- user profiles/settings use versioned high-level JSON under XDG config;
- target Ubuntu `.deb` packaging first;
- quick access is a compact second GTK window, not a new input driver.

## SX-CORE-002 · Harden platform service/backend — P0

**Status:** skeleton ready; live validation work remains.

Next backend work:

- validate live `oxpec` fan telemetry/attributes after module load;
- validate CPU boost/EPP write behavior before authorizing either;
- validate brightness write behavior in the active Ubuntu session;
- select and validate a package/APU power-target mechanism and range;
- define actual automatic fan recovery/rollback before enabling custom curves;
- keep charge-limit/bypass controls unavailable until a real interface is proven.

No frontend code may supply arbitrary sysfs paths or shell commands.

## SX-CORE-003 · Stable service/CLI status surface — P1

Use the typed `CapabilitySnapshot` / `CapabilityRecord` contract as the source of truth.

Target operations:

```text
GetSnapshot()
SetCapability(capability_id, value)     # only when can_write=true
ApplyProfile(profile)                   # later
ExportDiagnostics(options)              # later
```

D-Bus adapter and CLI may present the same service semantics.

## SX-UI-001 · GTK application shell + capability-driven UI — P0

**NEXT RECOMMENDED TASK.**

Build the GTK4/libadwaita shell against:

- `ServiceClient.get_snapshot()`;
- `CapabilitySnapshot`;
- `CapabilityRecord`;
- `ui_manifest.PAGES`.

Do not import hardware backends from UI code.

Every capability renders one of:

```text
CONFIRMED_LOCAL
SUPPORTED_UNVERIFIED
READ_ONLY
RESEARCH_PENDING
UNAVAILABLE
ERROR
```

### Tier-1 scope for first UI pass

Build all navigation/page shells and make them render read-only/disabled capability states correctly. Do **not** activate hardware writes in this task.

## SX-UI-002 · Dashboard — P1

Show:

- active profile placeholder/state;
- CPU/GPU temperature and useful power telemetry;
- internal fan state;
- battery;
- display mode;
- Frost Bay `RESEARCH_PENDING` card;
- Mini SSD presence + `NOT_QUALIFIED` warning;
- backend warnings/errors.

## SX-UI-003 · Performance page — P1

Render:

- CPU boost;
- EPP/performance preference;
- power-target status;
- observed power/thermal state;
- profile selection.

Unverified writes stay visibly disabled.

Reserve `Liquid Performance` as unavailable until Frost Bay research passes.

## SX-UI-004 · Cooling page — P1

Before fan writes are validated, render live/read-only status and the reason controls are disabled.

After validation:

- automatic/manual mode;
- duty/RPM;
- safe presets;
- custom curve only with tested recovery/rollback.

Frost Bay remains a separate `RESEARCH_PENDING` section pre-Astra.

## SX-UI-005 · Display page — P1

Render brightness and connected display/mode telemetry first.

Add mutation only after reliable compositor/session paths are validated for:

- brightness;
- resolution;
- refresh rate;
- VRR.

## SX-UI-006 · Power / Battery page — P1

Show battery state/capacity and performance context. Charge limit/bypass remain unavailable until proven.

## SX-UI-007 · Existing controller / vibration / gyro integration — P2

Prefer HHD/InputPlumber/Steam integration. Do not create a second controller stack.

## SX-UI-008 · RGB integration — P2

Search maintained Linux support first. If proprietary USB/HID archaeology is required, send it to Tier 3 before considering Tier 4. RGB does not block the pre-Astra gate.

## SX-UI-009 · Declarative profiles — P1

Profiles contain high-level policy only. Target names:

- Quiet;
- Balanced;
- Performance;
- Custom;
- Liquid Performance (defined but unavailable pre-Frost-Bay).

Transactional apply/rollback is required before multi-setting writes are considered production-ready.

## SX-UI-010 · Quick-access panel / hotkey — P1

Build a compact second GTK window using the same `ServiceClient` and capability contract.

Expose high-frequency controls/status. Prefer existing input/hotkey integration; do not write a new driver just to open the panel.

## SX-UI-011 · Game-aware profile association — P2

Optional after profiles work. Associate process/game identity with user-selected profiles without becoming another launcher.

## PRE-ASTRA GATE

- [x] trustworthy diagnostics/capability code foundation;
- [ ] refreshed live diagnostic snapshot from the hardened collector;
- [ ] polished GTK application shell/dashboard;
- [ ] CPU/performance write controls locally validated and available from UI where safe;
- [ ] internal fan control locally validated and available from UI;
- [ ] display controls available where Linux/session support is proven;
- [ ] battery telemetry and supported controls;
- [ ] declarative profiles;
- [ ] quick-access workflow;
- [ ] Mini SSD basic telemetry with `NOT_QUALIFIED` warning;
- [ ] Frost Bay visible as `RESEARCH_PENDING` with no guessed protocol path;
- [ ] unresolved ordinary features classified/documented.

---

# Phase 2 — Frost Bay deep research

Issue #4 remains the primary research mission.

## SX-FB-001 · Passive Frost Bay discovery — P0 / RESEARCH

Use Gemini Flash first for passive collection of device identity, advertisements, GATT map, reads and notifications. No unknown writes.

## SX-FB-002 · Static OneXConsole archaeology — P0 / RESEARCH

Use DeepSeek V4 Pro High first for vendor binary/resource inspection: names, UUIDs, packet structures, telemetry labels, command IDs, reconnect behavior, range/safety checks.

## SX-FB-003 · Astra protocol mission — P0 / RESEARCH

Give Astra the curated GATT + static-analysis evidence packet. Resolve only remaining semantics with the smallest safe experiments.

## SX-FB-004 · Linux read-only client — P1

Terra implements confirmed discovery/connection/telemetry semantics against the already-existing Frost Bay capability contract.

## SX-FB-005 · Minimum safe control POC — P1

First write must be understood, benign, reversible, identity-checked and rollback-ready.

## SX-FB-006 · State machine / fault handling — P1

Disconnected, stale, unknown or faulted never equals healthy.

## SX-FB-007 · Liquid-power safety gate — P1

Liquid-only profiles require fresh positive cooler health and a verified fallback.

---

# Phase 3 — Mini SSD deep research

Issue #5 remains the primary research mission.

## SX-SSD-001 · Refresh known-good baseline — P0

Use the hardened collector to capture current PCIe/NVMe/namespace/link/temp/SMART/kernel state.

## SX-SSD-002 · Reproduce disappearance systematically — P0 / RESEARCH

Astra High runs the bounded experimental matrix after Gemini/cheaper models reduce logs where useful.

## SX-SSD-003 · Determine failure layer — P0 / RESEARCH

Discriminate physical/contact, slot power, link training, ASPM, NVMe controller/reset/firmware, thermals, I/O/filesystem, or defective hardware.

## SX-SSD-004 · Test minimum mitigation — P1 / RESEARCH

Change one evidence-backed variable at a time and require repeatability.

## SX-SSD-005 · Reliability qualification — P1

Only after root cause/mitigation work run repeated boot/suspend/idle/read/write/checksum/thermal qualification.

## SX-SSD-006 · Production health monitor — P2

Only then replace `NOT_QUALIFIED` with evidence-backed qualified/degraded/fault states.

---

# Phase 4 — Integrate research discoveries

## SX-INTEGRATE-001 · Frost Bay production backend — P1

Activate the existing cooling UI only with confirmed protocol semantics.

## SX-INTEGRATE-002 · Liquid profile activation — P1

Enable only after cooler-health/fallback behavior is verified.

## SX-INTEGRATE-003 · Mini SSD qualified health states — P1

If the final answer is hardware/firmware unreliability, the UI must say that rather than manufacture a software success state.

---

# Phase 5 — Hardening and packaging

- **SX-HARD-001:** opt-in hardware regression suite.
- **SX-HARD-002:** safe startup/recovery.
- **SX-HARD-003:** D-Bus/polkit privilege review.
- **SX-HARD-004:** Ubuntu `.deb` packaging.
- **SX-HARD-005:** compatibility/diagnostic report.
- **SX-HARD-006:** broader ONEXPLAYER evaluation only after Super X is solid.

---

# Next model handoff

**Recommended:** Gemini 3.8 Flash (or DeepSeek V4 Flash) for `SX-UI-001`.

Task boundary:

> Build the GTK4/libadwaita application shell, navigation, Dashboard, and read-only page skeletons using only `ServiceClient`, `CapabilitySnapshot`, `CapabilityRecord`, and `ui_manifest.PAGES`. Correctly render `SUPPORTED_UNVERIFIED`, `READ_ONLY`, `RESEARCH_PENDING`, `UNAVAILABLE`, warnings and `NOT_QUALIFIED`. Do not wire hardware writes, D-Bus privilege code, Frost Bay protocol work, or Mini SSD stress testing.

After that pass, return to Terra for review and live backend integration.
