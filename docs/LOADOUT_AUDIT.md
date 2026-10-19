# Loadout fan/TDP audit — SX-UPSTREAM-001

**Audit status:** COMPLETE — 2026-10-18. Documentation only; no write authorization. **Source:**
`srsholmes/loadout`, commit `ac60b8030642d2a0249160ab4be555b061d206f1` (2026-10-05). Local clone HEAD and clean
worktree checked; all upstream citations below are repository-relative `path:start-end` at that commit.

Evidence labels follow [AGENTS.md](../AGENTS.md): **L1** = direct Super X observation; **L2** = kernel/official
documentation; **L3** = maintained open-source behavior; **L4** = static vendor evidence; **L5** = community
report; **L6** = hypothesis. Here **L3 means static inspection of implementation/tests, not an executed test or
local hardware result**. Recommendations are proposed project requirements, not L1. No Loadout script, binary,
installer or test was executed; no network/hardware access.

Local evidence remains [LIVE_INTEGRATION_HANDOFF.md](LIVE_INTEGRATION_HANDOFF.md) and
[LINUX_INTEGRATION.md](LINUX_INTEGRATION.md): their L1 baseline is kernel 7.0.0-30 with no live `oxp_ec`; the
2026-10-18 addendum adds L1 owner-routed writes for EPP (power-profiles-daemon) and brightness (GNOME Settings
Daemon) only. Kernel 7.0.0-38 still lacks the Super X quirk. **Fan
validation is blocked until the quirk is loaded.** Frost Bay is outside this audit. Discovery remains distinct from
authorization.

## 1. Algorithms/design patterns to adapt and contract mapping

The existing flow is `ServiceClient.set_capability` → `SuperXService.set_capability` → `PlatformBackend`; snapshots
return `CapabilityRecord` through the client. References: [UI_CONTRACT.md](UI_CONTRACT.md),
`src/superx_helper/client.py`, `contracts.py`, `service.py`, `platform.py`, and `capabilities.py` in that package.
The following mappings are proposed work, not functionality this audit implements.

### Hwmon discovery and sensor identity

**L3:** scans hwmon chip names and fan channels, associates RPM/PWM/enable nodes, then prefers the first PWM
device, RPM-target device, or telemetry-only fan. Temperature classification excludes battery/storage labels and
prefers die sensors over ACPI fallback. (`plugins/fan-control/backend.ts:504-525`,
`plugins/fan-control/backend.ts:1153-1253`, `plugins/fan-control/lib/sensors.ts:56-106`.) **Prevents:** dependence
on transient `hwmonN` and the wrong thermal zone. **Map:** reuse our `find_hwmon_by_name`/discovery; strengthen
`PlatformBackend` identity/channel checks for the qualified `oxp_ec`, not arbitrary first-writable hardware.
Service publishes availability/reasons; client receives no paths.

### `pwm1_enable` ownership capture/restore

**L3:** captures enable values on first logged discovery; unload restores each captured value, falling back to `2`
after a failed capture. Mapping is 0=full, 1=manual, 2=auto. (`plugins/fan-control/backend.ts:519-525`,
`plugins/fan-control/backend.ts:1586-1620`, `plugins/fan-control/lib/sensors.ts:109-121`.) **Prevents:** leaving a
temporary manual owner behind after orderly unload. **Map:** backend captures fresh mode/duty/identity before
acquisition; service owns the lease and recovery policy; client shows owner and recovery failure. Require
successful capture and qualified auto semantics, rather than copying the fallback. Captured manual ownership and
restoration to automatic are different guarantees.

### Persisted global mode, separate from temporary intent

**L3:** sanitizes auto/manual/preset/custom intent; merges storage updates; restores after discovery; keeps game
intent separate and restores the current global choice. (`plugins/fan-control/lib/global-mode.ts:24-72`,
`plugins/fan-control/backend.ts:375-389`, `plugins/fan-control/backend.ts:588-669`.) **Prevents:** restarts losing
intent or a temporary profile becoming the default. **Map:** service stores validated high-level intent; backend
rechecks identity, authorization and safety before applying it; client distinguishes desired/observed. Saved intent
never grants permission or bypasses safe startup/recovery.

### Serialized operations / mutex

**L3:** public fan intents queue on a promise lock; private helpers assume the lock is held; `finally` releases it.
(`plugins/fan-control/backend.ts:279-297`, `plugins/fan-control/backend.ts:710-726`,
`plugins/fan-control/backend.ts:864-874`.) **Prevents:** interleaved mode/profile transitions and recursive-lock
deadlock. **Map:** one service-side fan operation lock across all client/profile requests; backend primitives do
not re-enter public service methods. Recovery has explicit priority and must remain reachable when the normal
operation lane stalls.

### Stale curve ticks and teardown

**L3:** busy ticks skip rather than queue; start/stop increments a generation; queued ticks recheck it after taking
the lock. Unload invalidates ticks and drains normal operations before restoration.
(`plugins/fan-control/backend.ts:466-482`, `plugins/fan-control/backend.ts:1287-1322`.) **Prevents:** old curves
overwriting a new mode or reacquiring manual after exit. **Map:** service owns generation/cancellation and teardown
ordering; backend checks current ownership immediately before writes; client only reports committed state. Use
monotonic freshness and count verified successes, not merely completed calls.

### Bounded duty / clamping and curve validation

**L3:** linear interpolation, percent rounding/clamping and PWM conversion are pure; custom curves retain finite
points, clamp/sort/deduplicate, limit point count and fall back to defaults.
(`plugins/fan-control/lib/fan-curves.ts:46-90`, `plugins/fan-control/lib/custom-curve.ts:21-90`.) **Prevents:**
out-of-range writes and interpolation division by zero. **Map:** service rejects malformed/nonfinite/bool-as-number
requests and invalid profiles; backend enforces the locally qualified positive floor and upper bound for every
writer. Client receives that same range. Do not import zero-duty presets: upstream permits 0%, including Silent's
first point. (`plugins/fan-control/lib/fan-curves.ts:19-27`.)

### Write timeouts

**L3:** fan writes invoke `tee` with a 5000 ms timeout; the exec helper signals the child, then still awaits output
and exit. (`plugins/fan-control/backend.ts:99-103`, `plugins/fan-control/backend.ts:1873-1887`,
`packages/exec/src/index.ts:169-193`.) **Prevents/intends to prevent:** a wedged EC holding all normal operations
forever. **Map:** backend uses bounded, supervised I/O; service deadlines invalidate the operation and trigger
recovery; client gets failed/unknown outcome, never success. A signal is not proof that a kernel-blocked write
stopped or cannot complete late; prove containment before allowing a replacement owner or reporting recovery.

### Safety floor

**L3:** pure logic only raises the requested duty and forces maximum on missing or nonfinite temperature.
Executable constants are 80°C→60%, 85°C→100%, critical at 95°C; WARM=HOT=80 makes the nominal warm tier
unreachable; release is below 55°C. Older 75°C prose is stale. (`plugins/fan-control/safety-floor.ts:14-25`,
`plugins/fan-control/safety-floor.ts:53-82`, `plugins/fan-control/safety-floor.ts:100-188`,
`plugins/fan-control/backend.ts:1475-1485`.) **Prevents:** an unsafe user curve suppressing cooling at high
temperature. **Map:** backend safety clamp on every duty route, including profiles/recovery; service publishes
override/reason via safety state and desired versus observed; client cannot disable it. Qualify Super X sensors,
positive minimum and thresholds; none of the upstream numbers constitutes local calibration.

### Independent thermal watchdog

**L3:** a separate 2 s status timer invokes the watchdog outside the normal lock; it defers to an active curve only
while its last-write timestamp is <5000 ms old, then writes the floor itself, with manual-enable before PWM.
(`plugins/fan-control/backend.ts:444-461`, `plugins/fan-control/backend.ts:1488-1526`,
`plugins/fan-control/backend.ts:1664-1691`.) **Prevents:** normal manual/auto/curve paths leaving a hot machine
unsupervised. **Map:** service supervises freshness and ownership independently of client/UI; backend provides
qualified emergency actions. Independence must cover blocked status reads and daemon death, not just another timer
on the same event loop.

### Recovery to automatic

**L3:** watchdog release honors current manual intent or restores captured mode; unload restores captured ownership
after draining normal work. (`plugins/fan-control/backend.ts:1530-1620`, `plugins/fan-control/backend.ts:466-493`.)
**Prevents:** a temporary safety override permanently changing user intent. **Map:** distinguish normal override
release from fault/exit/crash recovery. For our fault recovery, invalidate manual work, restore verified firmware
auto, read back, then report success; an unverified restore is an error and blocks writes. No automatic rollback
exists in our current backend ([PHASE0_HANDOFF.md](PHASE0_HANDOFF.md)).

### Limits and tests to inherit as scenarios

**L3 inspection findings, not executed failures:**

- Missing temperature makes the watchdog return without action, unlike the per-write fail-to-max logic.
  (`plugins/fan-control/backend.ts:1466-1473`, `plugins/fan-control/safety-floor.ts:106-117`.) Our stale/missing
  sensor policy must explicitly enter a qualified failsafe and revoke manual control.
- `writeHwmon` checks child exit without read-back; internal duty writes return `{success:false}` on error, but
  `applyCurve` ignores that result and ticks update freshness afterwards. The watchdog also catches rejection
  without checking that result. (`plugins/fan-control/backend.ts:1284-1312`,
  `plugins/fan-control/backend.ts:1524-1526`, `plugins/fan-control/backend.ts:1664-1691`,
  `plugins/fan-control/backend.ts:1875-1887`.) Require verified-success freshness.
- Restore errors are logged; a captured `1` restores manual, not auto. Lifecycle cleanup alone establishes no crash
  recovery. (`plugins/fan-control/backend.ts:466-493`, `plugins/fan-control/backend.ts:1586-1620`.) Reject
  acquisition without a safe owner and prove independently supervised crash recovery.
- Read the mocked stale-loop/watchdog/restore scenarios at `plugins/fan-control/backend.test.ts:914-1107`,
  concurrent/stale-intent scenarios at `plugins/fan-control/backend.test.ts:1821-1917`, and unload/failure
  scenarios at `plugins/fan-control/backend.test.ts:2144-2171` and `plugins/fan-control/backend.test.ts:2204-2243`
  (L3 test definitions). The timeout test at `packages/exec/src/exec.test.ts:105-114` exercises a sleeping child
  through `runStreaming`, not a stuck kernel fan write or `runFull` recovery. These are useful future fake-I/O
  scenarios, not a local qualification certificate.
  Pure parsing/profile scenarios also appear in `plugins/fan-control/lib/custom-curve.test.ts:37-130`,
  `plugins/fan-control/lib/global-mode.test.ts:31-79` and
  `plugins/fan-control/lib/per-game-profiles.test.ts:113-172` (L3 test definitions).

## 2. Gaming Mode / SteamOS / Decky / Bun assumptions to exclude

- **L3:** root system plugin service, user overlay service, X11/Xwayland, input-group membership and working Steam
  are installation/runtime assumptions. (`README.md:44-58`.) Keep GTK unprivileged and use our narrow D-Bus/polkit
  boundary; no Steam session, overlay or input grab is a prerequisite for hardware safety.
- **L3:** CEF/Gamescope/React/Bun and optional Steam UI injection define the UI; Decky is acknowledged as
  inspiration, not this plugin API. (`README.md:235-245`, `README.md:400-403`.) Import algorithms only, not Decky
  APIs, TypeScript/Bun timers, RPC events, overlay shortcuts or plugin permissions.
- **L3:** game profiles bind Steam app IDs and launch/exit callbacks.
  (`plugins/fan-control/lib/per-game-profiles.ts:76-91`, `plugins/fan-control/lib/per-game-profiles.ts:121-141`.)
  Keep only the temporary intent/restore principle for SX-UI-009; do not add a game lifecycle dependency.
- **L3:** RPM-target ownership stops/starts `jupiter-fan-control`; ectool is another fallback.
  (`plugins/fan-control/backend.ts:898-918`, `plugins/fan-control/backend.ts:993-1011`.) Neither is an authorized
  Super X path.
- **L3:** TDP bundling targets immutable SteamOS and glibc 2.41; Apex settings heal across SteamOS updates and
  include board-specific boot changes. (`plugins/tdp-control/build-ryzenadj.sh:4-17`,
  `plugins/apex/backend.ts:40-49`, `plugins/apex/backend.ts:290-297`.) Do not transplant packaging, boot edits or
  auto-healing into Ubuntu; audit ABI/dependencies separately if needed.

## 3. Licensing and attribution

This is a source-license inventory and proposed reuse procedure, not a completed redistribution review.
**Recommendation: reimplement the patterns in Python.** Independent lock/generation/interpolation/state-machine
designs need no source transplant; preserve this provenance. A close translation, copied tests/comments, tables or
substantial structure is direct reuse, even in a different language.

**L3 license evidence:** root `LICENSE:1-28` is BSD-3-Clause, copyright 2026 Simon Holmes. `NOTICE:1-11` points to
component notices; `THIRD_PARTY_LICENSES.md:3-11` explicitly leaves runtime/build dependencies for a separate
audit. Root BSD alone does not cover every bundled component.

| Reviewed source | Terms / consequence if directly reused |
|---|---|
| Fan control | BSD-3-Clause, Simon Holmes: `plugins/fan-control/LICENSE:1-29`. |
| TDP plugin source | BSD-3-Clause: `plugins/tdp-control/LICENSE:1-29`; binary exception in `plugins/tdp-control/NOTICE:5-20`. |
| Battery tracker | BSD-3-Clause: `plugins/battery-tracker/LICENSE:1-29`. |
| RGB control | BSD-3-Clause: `plugins/rgb-control/LICENSE:1-29`; HHD protocol provenance in `plugins/rgb-control/NOTICE:5-34`. |
| Apex capability integration | BSD-3-Clause: `plugins/apex/LICENSE:1-29`; package DMI code falls under root license (`LICENSE:1-28`). |

For BSD source reuse, retain the exact applicable copyright, all three conditions and disclaimer in source;
reproduce them in binary distribution documentation; do not imply endorsement (`LICENSE:3-28`,
`plugins/fan-control/LICENSE:3-29`, L3). Add a provenance entry naming original paths, full commit, changes, and
license, for example: “Portions adapted from Loadout fan-control, Simon Holmes, 2026; BSD-3-Clause; commit
ac60b8030642d2a0249160ab4be555b061d206f1.” This proposed summary supplements, and cannot replace, the complete
license text.

For a future TDP transplant, carry the applicable plugin NOTICE alongside the BSD attribution and identify any
bundled RyzenAdj separately as LGPL, with its source pin and license materials
(`plugins/tdp-control/NOTICE:1-20`, L3); omit binary-bundling claims if no binary is redistributed.

**L3:** TDP NOTICE identifies bundled RyzenAdj as LGPL-3.0, with license and source pin; SOURCE lists v0.19.0 /
`5775fc3`. The build folds libryzenadj into the CLI, although NOTICE discusses dynamic system libraries and
relinking. (`plugins/tdp-control/NOTICE:7-20`, `plugins/tdp-control/bin/linux-x64/SOURCE.txt:1-7`,
`plugins/tdp-control/build-ryzenadj.sh:65-80`.) Do not copy this binary under BSD or treat NOTICE plus a source URL
as a complete compliance determination. Any future redistribution must review corresponding-source/build delivery,
replaceability/relinking as applicable, changes, and both GPLv3/LGPLv3 texts; the supplied LGPL incorporates GPLv3
and specifies combined-work obligations. (`plugins/tdp-control/bin/linux-x64/LICENSE-ryzenadj:9-11`,
`plugins/tdp-control/bin/linux-x64/LICENSE-ryzenadj:79-126`, L3 license text.)

**L3:** RGB NOTICE credits GPL-3.0 HHD contributors for protocol facts and says no HHD code was
copied/transliterated (`plugins/rgb-control/NOTICE:5-27`). Retain that provenance if adapting this material; direct
HHD source reuse needs its own license review. NOTICE's `lib/drivers/*` layout does not describe this checkout's
actual backend/helper layout (`plugins/rgb-control/backend.ts:1-19`, `plugins/rgb-control/backend.ts:704-735`);
attribute files actually used. No code, bundled binary, or license text is being imported by this audit.

## 4. TDP strategy, Strix Halo suitability, and SX-CORE-004 rubric

**L3 strategy:** known ASUS/Lenovo WMI paths first; AMD RyzenAdj (bundled before PATH) next; Intel RAPL paths, then
coarse `platform_profile`, otherwise none. RyzenAdj availability selects it even if its STAPM read probe fails;
comments assert Strix Halo writes can work without reads. That assertion is upstream evidence only.
(`plugins/tdp-control/backend.ts:1404-1510`.)

**L3 writes:** RyzenAdj sets STAPM/fast/slow limits equally in milliwatts; RAPL uses microwatts; WMI writes three
limits sequentially. Success records a tracked wattage; reads may be measured, tracked, or estimated from platform
profile. (`plugins/tdp-control/backend.ts:627-693`, `plugins/tdp-control/backend.ts:1747-1812`,
`plugins/tdp-control/backend.ts:1831-1860`.) A command succeeding is not read-back.

**L3 policy:** desired power is separated from AC/battery-clamped output, persisted manual intent is separate from
automatic applies, and boost policy is reapplied with TDP (default off, best-effort failure). Unknown AC allows the
full ceiling. (`plugins/tdp-control/backend.ts:591-650`, `plugins/tdp-control/backend.ts:1160-1185`,
`packages/devices/src/devices.ts:414-433`.) Reuse intent separation, not silent boost changes, unknown-AC
permissiveness, or automatic upward reapplication.

**L3 caveat:** the Super X table proposes 5–90 W, battery 65 W and 15/45/75 W presets, while the global battery cap
reduces that to 55 W. None is our validated envelope. (`packages/devices/src/devices.ts:131-141`,
`packages/devices/src/devices.ts:414-433`.) The published tested list omits Super X (`README.md:219-228`). Do not
infer qualification from a matching DMI row.

**Assessment/recommendation:** suitability for this Strix Halo unit is unresolved. The source describes RyzenAdj as
SMU-mailbox/MMIO writes (`plugins/tdp-control/backend.ts:1432-1458`, L3); it is not an `oxpec` fan adapter. Treat
any proposed raw EC or SMU mechanism as privileged hardware control with partial-write, contention, firmware-reset
and unverifiable-state risks. Preserve firmware thermal protections; require documented limits and reversible
evidence. EPP or observed package power alone cannot prove a package-limit write succeeded.

SX-CORE-004 must compare the following without choosing a backend in this audit:

| Candidate | Evidence required before selection |
|---|---|
| Kernel/firmware interface | Exact Super X support; semantic limits/units; read-back; firmware ownership; recovery and maintained ABI. A coarse profile must not promise exact watts. |
| Maintained HHD integration | Pin/audit the actual power-control option and device mapping; determine its underlying interface, privilege, observable state and external-owner API. Do not run competing writers. |
| RyzenAdj adapter | Exact build/APU/firmware support; independent limit read-back if `--info` fails; safe partial-failure restoration; Ubuntu ABI and source/license packaging review. |

HHD is a reference in [UPSTREAM_OWNERSHIP.md](UPSTREAM_OWNERSHIP.md), but no pinned HHD power source was
supplied/reviewed offline here. Do not assume a particular current HHD option supports Super X. Prefer the
candidate with the narrowest maintained interface that proves identity, bounds, observation, exclusive ownership
and restore. Reject candidates that cannot prove these; keep `performance.power_target.can_write=false`. No backend
is selected.

## 5. OneXPlayer detection, battery charge control, and RGB

**L3 detection:** case-normalized vendor OR product-family detection is deliberately broad; Apex-specific board
identity remains separate. The Apex plugin enables family detection but gates board wiring separately.
(`packages/devices/src/dmi.ts:40-90`, `plugins/apex/backend.ts:243-272`.) Reuse per-feature discovery and separate
board identity; family membership alone cannot authorize EC layouts, GPIO fixes, HID writes or power ranges on
Super X.

**L3 battery:** discovers generic power_supply controls; checks exact enumerated `inhibit-charge`/awake tokens;
vendor-gates legacy `charge_type`; validates whole 50–100% limits. (`plugins/battery-tracker/backend.ts:248-297`,
`plugins/battery-tracker/lib/charge-control.ts:46-107`.) Reuse capability-specific parsing/range validation;
independently prove our device's semantics and range. Presence detection accepts non-ENOENT/non-ENODEV read
failures, and reporting can fall back to persisted intent for unreadable thresholds.
(`plugins/battery-tracker/backend.ts:343-417`, L3.) Keep present, readable, desired and observed separate;
EINVAL/EIO/EACCES and saved intent cannot establish success. Charge writes/restores need independent
before/read-back/restore evidence; current `power.charge_control` stays unavailable
([UI_CONTRACT.md](UI_CONTRACT.md), service).

**L3 RGB:** selects OXP HID V2, OpenRGB, generic LEDs, then platform-specific LEDs; HID detection checks 1A2C:B001
and descriptor usage page, and writes serialize with a 50 ms completion-to-next-write gap. Dependent effect/color
writes stop after brightness-enable failure. (`plugins/rgb-control/backend.ts:46-134`,
`plugins/rgb-control/backend.ts:230-267`, `plugins/rgb-control/backend.ts:524-560`.) Reuse narrow
identity/capability probes, serialization, prerequisite failure and partial-state reporting. Do not reuse
shell-string probes or initial cached color/mode as observation (`plugins/rgb-control/backend.ts:155-172`,
`plugins/rgb-control/backend.ts:251-264`, L3). Super X HID identity, LEDs, timing, read-back and controller-owner
coexistence remain unverified; `device.rgb` stays unavailable until a maintained path passes local qualification.

## 6. Local Super X validation still required

This is an uncompleted checklist, not permission to perform experiments now.

- [ ] Record a fresh redacted baseline for the validation kernel/module/firmware; do not rewrite historical L1.
- [ ] Verify the loaded Super X quirk and `oxp_ec` identity; see section 7.
- [ ] Qualify RPM, PWM, enable values and the actual CPU/APU hot-zone sensor(s), including missing/stale/error
  behavior, refresh cadence and plausibility.
- [ ] Establish conservative positive duty floor, safe temperature envelope, stop conditions and an independently
  usable firmware-auto recovery path.
- [ ] Prove ownership, before/read-back/restore, timeout/late-write containment, normal exit, daemon crash/restart
  and suspend/resume recovery (section 7).
- [ ] Revalidate competing owners and device identity after restart/re-enumeration; test fake-I/O failures first,
  with no physical writes in default tests.
- [ ] Qualify CPU boost under SX-CORE-003 before fan (EPP and brightness passed through their owners on
  2026-10-18); this audit does not complete that task or authorize TDP.
- [ ] For SX-CORE-004, audit pinned HHD/native/RyzenAdj candidates, independent limit read-back, AC/battery
  transitions, firmware resets and restore evidence.
- [ ] For later battery/RGB work, prove each interface and restore behavior independently; retain
  unavailable/unknown states where observation is absent.

## 7. ACCEPTANCE CRITERIA — SX-CORE-002 and fan ownership/recovery

### Must prove before `cooling.internal_fan.can_write` can become true

All items are required. Hardware portions belong to a later explicit, supervised, opt-in task with disposable
software fixtures first, a documented stop procedure and no simultaneous power increase. Do not disable firmware
thermal protections.

1. **Backport identity:** record kernel release, module build/source/patch identity, Super X DMI match and loaded
   driver binding; prove the Super X quirk is active, not merely that an `oxpec` module file is installed. No
   quirk/no hwmon = blocked.
2. **Target identity:** resolve `oxp_ec` by name and device/driver linkage, record channel ownership and
   `fan1_input`, `pwm1`, `pwm1_enable`; reject ambiguous or missing attributes. Re-enumeration must not redirect
   writes to another fan.
3. **Telemetry sanity:** record time-series RPM and hot-zone temperatures at idle and a bounded ordinary workload.
   Demonstrate plausible units/cadence, RPM response, and rejection of missing, malformed, frozen or implausible
   readings. A duty register alone does not prove spinning fans or safe cooling.
4. **Enable semantics live:** demonstrate read-back and physical RPM behavior for 2=firmware auto, 1=manual and
   0=full-speed on this driver/unit. These are only L2 expectations in the existing handoff, not local facts. Prove
   auto/restore first; test a modest safe manual step before any brief full-speed-mode test. Mode 0 is not PWM duty
   0; **never request zero duty**, stop fans or test max first. The mode-0 demonstration is optional and is NOT a
   prerequisite for enabling manual duty; skip it if any doubt exists about thermal headroom.
5. **Read before write:** capture current identity, mode, duty, RPM and thermals before each ownership transaction.
   Failed/unknown capture aborts acquisition; contested ownership blocks it. Start qualification from verified
   firmware auto, rather than inheriting an unexplained manual owner.
6. **Qualified bounds:** establish a conservative nonzero running/start floor and upper bound with evidence,
   without approaching stall. Enforce them server-side for direct requests, curves, profiles, startup and watchdog.
   Reject nonfinite, wrong-type and out-of-range input; align the advertised range. Current 0–100% contract/backend
   acceptance is not sufficient qualification.
7. **Verified transaction:** confirm manual-enable before duty; read back each requested value within documented
   tolerance/deadline and observe RPM. If any prerequisite fails, no dependent write occurs; partial failure enters
   recovery and returns failed `OperationResult`, with actual observed or unknown state.
8. **Normal/fault recovery:** invalidate all manual work, drain/contain outstanding I/O, restore `pwm1_enable=2`,
   read back auto and observe firmware-driven behavior after manual/curve use, failed duty write, explicit auto,
   client disconnect, service stop and shutdown. Prove no stale operation can reacquire manual later.
9. **Crash recovery:** demonstrate daemon exception, forced termination, hung normal loop and restart using an
   independent supervisor/recovery mechanism that can restore and verify auto within a recorded safe deadline. An
   unload callback cannot cover daemon death. Startup must recover before replaying saved intent; repeat after
   suspend/resume. If recovery is unprovable, keep writes disabled.
10. **Serialization/stale work:** fake-I/O traces must prove concurrent mode/profile changes serialize; queued old
    generations and overrun ticks cannot overwrite new intent or post-restore auto. Demonstrate the same service
    ordering during the later bounded live pass; do not create uncontrolled competing writers.
11. **Bounded failures:** inject denied writes, mismatch, absent node, timeout and late completion in fixtures.
    Prove bounded response, lock release, no false success/freshness and no post-recovery write from a timed-out
    operation. A truly blocked kernel/EC is not solved by a timer: document the containment ceiling and
    independently verified fallback; otherwise fail this criterion.
12. **Floor/watchdog:** simulate hot, critical, stale, missing and malformed sensor inputs before supervised live
    validation. Prove every writer respects the calibrated floor, the watchdog acts despite normal-lock/status/UI
    stalls, and release hysteresis cannot undo an active safety override. Missing/stale telemetry enters the
    qualified failsafe; it never means cool/healthy.
13. **Recovery failure:** inject an auto-restore failure; prove a visible error, revoked manual authorization, no
    automatic retry into manual and a documented locally qualified emergency fallback. Never claim auto was
    restored without observation; keep firmware protection intact throughout.
14. **Evidence and authorization:** save the packet below, review every result, then separately authorize only the
    proven manual/auto/range/mode scope. Service and backend both gate requests; client uses derived `can_write`
    only. Validate behavior when authorization is removed. A passing manual test does not authorize custom curves
    or a power increase without their own criteria.

Record one redacted evidence packet per run: UTC plus monotonic timestamps; kernel/module/quirk/BIOS identity;
resolved hwmon/device/sensor identities; owner and authorization; requested mode/duty and bounds; before →
write/read-back → restore/read-back with raw values, units, RPM and thermals; per-step deadlines; failure injection
and last verified-success time; recovery initiator/results; post-recovery observation interval; pass/fail against
each numbered item; logs, reviewer and unresolved limitations. Never put unique identifiers or personal filesystem
data in default diagnostics. Record aborts as failures, not omissions.

### Nice to have after the required gate

- Larger acoustic/RPM efficiency characterization and user-selectable curves within the already qualified envelope;
  not grounds to lower a safety floor.
- Longer multi-kernel/firmware regression history and broader OneXPlayer support.
- Per-game intent integration and richer plots. Neither is needed for a safe single-capability manual/auto adapter;
  defer under SX-UI-009/UI polish.

## 8. Concrete adaptation plan (no implementation in this change)

These are bounded sub-items of existing roadmap work, not new roadmap commitments. Tier names follow AGENTS.md: T1
Gemini 3.8 Flash/DeepSeek V4 Flash; T2 GPT-5.6 Terra; T3 DeepSeek V4 Pro for demonstrated hard debugging; T4 Astra
only after maintained upstream evidence is exhausted. No T4 work is justified by this audit.

| Order / ID | Small scope and deliverable | Tier | Depends on |
|---|---|---|---|
| 1 · SX-UPSTREAM-001/A | This pinned audit, gaps, license inventory and acceptance packet template. Complete 2026-10-18. | T1 docs; T2 review | Existing contracts/handoff |
| 2 · SX-CORE-002/A | Plan/review the exact Super X quirk backport or containing kernel and rollback boot path; record provenance. | T2 | 1 |
| 3 · SX-CORE-002/B | Later opt-in read-only binding/identity/sensor inventory after the quirk is loaded; stop if absent/ambiguous. | T2 | 2 |
| 4 · SX-CORE-002/C | Adapt the existing Python fan methods: fresh ownership capture, positive bounds, verified mode/duty/auto, bounded I/O and failure results. Leave production authorization empty. | T2 | 1, 3 |
| 5 · SX-CORE-002/D | Add service serialization, generation checks, independent recovery/watchdog supervision and verified-success freshness; no UI hardware knowledge. | T2 | 4 |
| 6 · SX-CORE-002/E | One focused fake-I/O scenario suite covering section 7 failures, concurrency, teardown, sensor loss and crash supervision; no physical writes. | T1; T2 review | 4, 5 |
| 7 · SX-CORE-002/F | Explicit live before/read-back/restore qualification and ownership/crash recovery packet; classify failures, authorize nothing on incomplete proof. | T2; T3 only for unexplained failures | 3–6; SX-CORE-003 boost pass (EPP/brightness done via owners) |
| 8 · SX-UI-004/A | Enable only qualified fan scope through ServiceClient; expose auto/recovery/override and honest desired/observed values. Curves remain gated until proven. | T1; T2 gate review | 7; SX-CORE-005 production boundary |
| 9 · SX-CORE-004/A | Pin/audit native, HHD and RyzenAdj candidates using section 4; produce decision/range/restore evidence requirements before any backend selection. | T2 | 1; source intake authorized separately |
| 10 · SX-UI-009/A | Persist sanitized global intent separately from temporary profiles; gate replay and transactional recovery. Add curves only after their ownership/watchdog proof. | T2 backend; T1 UI | 5–8; relevant qualified capabilities |
| 11 · SX-UI-006/008/A | Later narrow battery/RGB interface audits and validation packets; retain unavailable state until each passes. | T2; T1 presentation | 1; maintained interface evidence |

SX-CORE-003's ordinary writes, SX-CORE-004's backend choice, SX-CORE-005's deployment boundary and the internal-fan
PRE-ASTRA gate remain open. Completing this audit only clears the upstream-audit gate; it supplies no local fan/TDP
write evidence.
