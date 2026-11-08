# Strix Halo TDP backend audit — SX-CORE-004

**Audit date: 2026-11-08. Status: docs-only source audit complete; backend selection OPEN.**
Nothing in this document authorizes a write, a root operation, installation, module loading or a kernel change.
Discovery is not authorization. Keep `performance.power_target.can_write=false` until separate local qualification
and explicit policy authorization. No Super X wattage limit is recommended here.

## 1. Scope, pins and evidence

All candidate citations use repository-relative `path:start-end` at these pins. Prefix **P:** means PowerStation;
**O:** means oxp-x2mini. They are not references to moving branches.

| Prefix | Source | Inspected pin |
|---|---|---|
| P | [ShadowBlip/PowerStation](https://github.com/ShadowBlip/PowerStation/tree/1e5b36b5a96ae6904e8a23a5dfbb10e0b674e53d), tag v0.9.0 | `1e5b36b5a96ae6904e8a23a5dfbb10e0b674e53d` (2026-11-01) |
| O | [dahui/onexplayer-x2-mini-pro-cachyos](https://github.com/dahui/onexplayer-x2-mini-pro-cachyos/tree/62c37310a4d86f9c6252e535c3e53b22668d2a49) | `62c37310a4d86f9c6252e535c3e53b22668d2a49` (2026-09-26); daemon under `tdpd/` |

Evidence labels exactly follow [LOADOUT_AUDIT.md](LOADOUT_AUDIT.md): **L1** = direct Super X observation;
**L2** = kernel/official documentation; **L3** = maintained open-source behavior; **L4** = static vendor evidence;
**L5** = community report; **L6** = hypothesis. Here **L3 means static inspection of implementation/tests, not an
executed test or local hardware result**. Upstream prose describing measurements is L5 even when stored at a pinned
source path. Proposals below are project requirements, not observations. Negative findings describe the inspected
paths, not proof about unavailable dependencies or all possible runtime behavior.

Both clone HEADs matched the supplied pins. Only text and git metadata were read; no upstream program, build,
installer or test was executed, no upstream instructions were followed, and no network/hardware access occurred.
The implementation rubric and validation model are [Loadout sections 4, 7 and 8](LOADOUT_AUDIT.md).
The main checkout's read-only research refresh is background supplied by the coordinator; its claims are not
automatically promoted to inspected implementation. Its absolute location is
`/home/dq/Projects/Super-X-Helper/docs/research/2026-11-08-upstream-refresh.md`, with companion section “2026-11-08 research refresh” in that checkout's `docs/UPSTREAM_OWNERSHIP.md`.

**L1, supplied development-machine observations, 2026-11-08 (not recaptured in this audit):** Super X, Ryzen AI
MAX+ 395, Strix Halo family 1Ah, kernel `7.0.0-42-generic` (newest noble HWE in the supplied inventory); amdgpu
hwmon has no `power1_cap`; no `/sys/firmware/acpi/platform_profile` or firmware-attributes class; `amd_pmf` loaded;
powercap `intel-rapl` exposes `package-0`/`core` telemetry, not qualified writes; PPD 0.21 is the qualified EPP
writer; no installed `ryzen_smu`. These replace no historical baseline. A loaded PMF module, telemetry, or a
candidate's model-table match does not establish a package-power write interface. EPP/brightness remain the only
production-qualified write capabilities; no code/policy changes are part of this audit.

**L5 external leads supplied, not fetched:**

- [amkillam/ryzen_smu #27](https://github.com/amkillam/ryzen_smu/issues/27): family-1Ah SMN access via C4/C8 was
  reported incorrect and fixed with kernel `amd_smn_*` accessors; wedged GPU power management was reported.
  The driver source containing that fix is not among the supplied clones. Exact fix commit, inclusion in a proposed
  module and compatibility with this Ubuntu kernel remain unverified; a PM-table patch alone is insufficient.
- [PowerStation #43](https://github.com/ShadowBlip/PowerStation/issues/43): Strix Halo GPU misclassification and an
  old vendored RyzenAdj were reported; issue closed 2026-08-28. Closure is not a local qualification certificate.
  The inspected code now queries DRM and locks a 0.19.0 wrapper (P:`src/performance/gpu/drm.rs:18-28`,
  P:`src/performance/gpu/drm.rs:105-125`, P:`Cargo.lock:637-656`, L3).
- AMD DPTCi RFC for ALIB power controls exists but is not in stock Ubuntu, per supplied lead:
  [RFC](https://lkml.indiana.edu/2603.1/02794.html). No RFC/kernel implementation was supplied for inspection.

## 2. Candidate: PowerStation v0.9.0

### Identity, coverage and bounds

**L3:** GPU discovery reads PCI identity under the DRM card, asks DRM whether it is integrated and falls back to
PCI class guessing if the query fails. For amdgpu the query checks `AMDGPU_IDS_FLAGS_FUSION`; only a GPU classified
`integrated` gets the AMD TDP interface. Thus the new query addresses the misclassification mechanism, but failed
queries can still hit the old heuristic. (P:`src/performance/gpu/dbus/gpu.rs:287-333`,
P:`src/performance/gpu/drm.rs:84-125`, P:`src/performance/gpu/amd/amdgpu.rs:34-47`.)

**L3:** range lookup prefers a recognized DMI product name, then CPU model string, using case-insensitive equality;
DMI overrides take priority in the merged databases. There are explicit `ONEXPLAYER SUPER X` and
`AMD Ryzen AI Max+ 395 w/ Radeon 8060S` entries. Their advertised numbers differ: DMI 8/80 W min/max and 20 W
max boost; CPU 45/130 W and 30 W max boost. These are upstream configuration, **not qualified Super X bounds**.
An unmatched model leaves zero-valued limits. (P:`src/performance/gpu/platform/hardware.rs:32-80`,
P:`src/performance/gpu/platform/hardware.rs:119-178`,
P:`rootfs/usr/share/powerstation/platform/dmi_overrides_apu_database.toml:139-143`,
P:`rootfs/usr/share/powerstation/platform/amd_apu_database.toml:655-659`.)

**L3 gap:** min/max/max-boost getters expose hardware configuration, but the RyzenAdj setters enforce only TDP
`<1` and boost `<0` rejection; they do not enforce those advertised maxima/minima or explicitly reject nonfinite
values before float-to-integer conversion. A database match proves neither firmware support nor an enforced
safety envelope. (P:`src/performance/gpu/tdp.rs:41-69`, P:`src/performance/gpu/amd/ryzenadj.rs:286-351`.)

### Transport, units and STAPM/PPT semantics

**L3:** AMD TDP reads/writes try ASUS WMI, then hwmon, then RyzenAdj, logging errors and trying the next interface.
The hwmon implementation uses labels `slowPPT`/`fastPPT`, with W scaled by 1,000,000 for sysfs units. The local
absence of cap nodes rules out assuming this path works on the supplied L1 baseline; discovery alone can still
construct a hwmon object. (P:`src/performance/gpu/amd/tdp.rs:97-191`,
P:`src/performance/gpu/amd/hwmon.rs:10-25`, P:`src/performance/gpu/amd/hwmon.rs:29-105`, L3; local absence L1.)

**L3:** the fallback constructs `libryzenadj::RyzenAdj` and calls `set_stapm_limit`, `set_slow_limit`,
`set_fast_limit`; D-Bus watts become integer milliwatts. It is not an oxpec/EC interface. `set_tdp(T)` first reads
boost, writes STAPM=T, then calls `set_boost(B)`: slow=T+B and fast=1.25×(T+B). `boost()` computes slow−STAPM,
although the D-Bus comment describes fast−STAPM. The computed boost can be negative, which the subsequent setter
rejects after STAPM has already changed. STAPM alone must not be represented as a hard short-term ceiling.
(P:`src/performance/gpu/amd/ryzenadj.rs:4-8`, P:`src/performance/gpu/amd/ryzenadj.rs:59-68`,
P:`src/performance/gpu/amd/ryzenadj.rs:87-98`, P:`src/performance/gpu/amd/ryzenadj.rs:118-135`,
P:`src/performance/gpu/amd/ryzenadj.rs:165-183`, P:`src/performance/gpu/amd/ryzenadj.rs:286-351`,
P:`src/performance/gpu/dbus/tdp.rs:68-75`.)

**L3 boundary / L6 unresolved transport:** Cargo locks `libryzenadj` and `libryzenadj-sys` 0.19.0 to
`a57076cc4f1e4012f6dd53831619d45a3c9e7375`; it does not include their implementation in this clone.
The exact underlying C RyzenAdj pin, Strix Halo family dispatch, MP1/RSMU selection, SMN accessor fix, kernel-module
selection and raw-memory fallback cannot be certified from these Rust calls. O's independently inspected code
provides a dispatch reference, not proof of P's dependency behavior. Do not repeat the refresh's “vendored RyzenAdj
0.19.0” as an audited C-source identity. (P:`Cargo.toml:33-34`, P:`Cargo.lock:637-656`,
P:`src/performance/gpu/amd/ryzenadj.rs:87-98`, P:`src/performance/gpu/amd/ryzenadj.rs:165-183`.)

### Observation versus intent

**L3:** supported-device getters call `refresh()` and library limit getters, but a refresh error is logged and
execution proceeds to the getter. TDP reads STAPM; boost reads slow and STAPM; the fast getter is private and named
`_get_ppt_limit_fast`, not an independent D-Bus fast-limit property. Van Gogh/Sephiroth GPU IDs use cached/fake
STAPM/fast/thermal values; Super X is not in that exception list. Setters return on library success, without a
post-write refresh/compare of all three limits. Consequently the API intends hardware observation for Super X,
but freshness, PM-table layout and transactional verification remain unproved here; a successful setter is not
read-back. (P:`src/performance/gpu/amd/ryzenadj.rs:43-58`, P:`src/performance/gpu/amd/ryzenadj.rs:82-115`,
P:`src/performance/gpu/amd/ryzenadj.rs:137-211`, P:`src/performance/gpu/amd/ryzenadj.rs:277-351`.)

**L3:** `PowerProfile` is a cached string initially `power-saving`, explicitly not a measured value; setting it
calls RyzenAdj power-saving/max-performance controls and then caches intent. It must not stand in for PPD's EPP
or observed package limits. (P:`src/performance/gpu/amd/ryzenadj.rs:39-41`,
P:`src/performance/gpu/amd/ryzenadj.rs:258-273`, P:`src/performance/gpu/amd/ryzenadj.rs:367-383`.)

### Privilege, D-Bus and competing writers

**L3:** system bus name `org.shadowblip.PowerStation`; TDP interface `org.shadowblip.GPU.Card.TDP` on discovered
`/org/shadowblip/Performance/GPU/CardN` objects. Standard `org.freedesktop.DBus.Properties.Get/GetAll/Set` methods
operate on TDP properties, rather than a custom transaction method. Writable doubles: `TDP`, `Boost`,
`ThermalThrottleLimitC`; writable string: `PowerProfile`; read-only doubles: `MinTdp`, `MaxTdp`, `MaxBoost`;
read-only string array: `PowerProfilesAvailable`. The supplied XML/README is less complete than the implementation,
so bind to the inspected implementation and later verify actual introspection.
(P:`src/constants.rs:1-4`, P:`src/main.rs:24-55`, P:`src/performance/gpu/amd/amdgpu.rs:34-47`,
P:`src/performance/gpu/dbus/tdp.rs:32-138`, P:`bindings/dbus-xml/org-shadowblip-gpu-card.xml:48-70`,
P:`README.md:129-134`.)

**L3:** the system unit has no `User=` override; the bus policy allows only root to own the name but **any sender**
to send to it. Setters take a per-device Tokio mutex and directly invoke operations; there is no per-caller polkit
check in this path. This is broader than the intended Super X Helper authorization boundary. Merely wrapping it
with our facade would leave the original writable bus API reachable unless its policy is also restricted.
(P:`rootfs/usr/lib/systemd/system/powerstation.service:1-9`,
P:`rootfs/usr/share/dbus-1/system.d/org.shadowblip.PowerStation.conf:5-12`,
P:`src/performance/gpu/dbus/tdp.rs:32-49`, P:`src/performance/gpu/dbus/tdp.rs:86-129`.)

**L3 bounded absence finding:** that mutex serializes this object's callers, not another TDP daemon, HHD,
RyzenAdj CLI or firmware/kernel work. The inspected dispatch/setter paths contain no cross-process lease,
PPD/HHD handoff or mailbox arbitration; fallback after interface failure is also not rollback.
(P:`src/performance/gpu/dbus/tdp.rs:32-49`, P:`src/performance/gpu/amd/tdp.rs:147-191`,
P:`src/performance/gpu/amd/ryzenadj.rs:286-351`.) **Proposal:** keep PPD as sole EPP owner; do not invoke P's
`PowerProfile`, thermal-limit or unrelated CPU/GPU controls as a side effect of TDP. Prove PPD profile transitions
and firmware responses do not reset or fight the chosen package limits; disable/handoff other package-limit
writers before any live acquisition. No current pinned HHD implementation was supplied, so HHD compatibility is
**L6 unresolved**, not an inferred feature.

### Failures, timeouts and restoration

**L3:** library errors propagate to D-Bus Failed/IOError; refresh failures can be followed by getters, slow values
below 1 cause boost=0, and multi-limit changes can stop halfway with no compensating restore. The per-object lock
has no deadline/debounce around these library calls. Main registers interfaces and waits forever; the supplied
unit has no restore `ExecStop` or independent recovery action. No capture/restore lifecycle is implemented in
these inspected paths. Crash or orderly-exit firmware restoration is therefore **not established**; exact
lower-library timeout/wedge behavior is **L6 unknown**. (P:`src/performance/gpu/dbus/tdp.rs:15-22`,
P:`src/performance/gpu/dbus/tdp.rs:43-49`, P:`src/performance/gpu/amd/ryzenadj.rs:100-115`,
P:`src/performance/gpu/amd/ryzenadj.rs:286-351`, P:`src/main.rs:81-92`,
P:`rootfs/usr/lib/systemd/system/powerstation.service:1-9`.) The family-1Ah wedging lead remains L5 (§1), not a
verified P-specific failure or an assertion that a userspace timeout repairs the SMU.

### Ubuntu 24.04 / kernel 7.0.0-42 and licensing

**L3 packaging inventory:** Rust 2021 project with Tokio/zbus, udev, git-sourced rog_platform and libryzenadj;
lockfile pins the wrapper; reference Dockerfile uses Rust 1.88, cmake, libpci and libclang development packages.
Makefile distributes a tar archive and RPM and installs binary, unit, D-Bus policy and platform databases.
(P:`Cargo.toml:1-34`, P:`Cargo.lock:637-656`, P:`Dockerfile:1-13`, P:`Makefile:30-42`, P:`Makefile:90-112`.)
**L6 feasibility proposal:** a reviewed native Ubuntu `.deb` is plausible, but neither a noble build/ABI result
nor dependency license closure was established. Rust 1.88 is a reference build image, not a proven minimum MSRV.
No exact required `ryzen_smu` version or compatibility with `7.0.0-42` can be derived from the absent library/driver
sources. Retrieve and audit the locked dependency tree and choose a pinned family-1Ah-correct transport before
root/install approval; do not weaken `/dev/mem` protections to make read-back work.

**L3 license inventory:** P declares GPL-3.0-or-later. Copied source/close translations require retaining notices
and license, marking modifications and observing whole-derived-work/source-delivery requirements on distribution.
(P:`Cargo.toml:1-6`, P:`README.md:145-147`, P:`LICENSE:195-228`, P:`LICENSE:245-286`.)
**Proposal:** independent Python design work should record upstream paths/pin and adopted invariants; do not copy
tables, tests or implementation structure under the label “design only.” A separate service client is preferable
to transplanting code, but any bundled service/dependencies still need their own distribution inventory.
**L6 unresolved:** the wrapper and underlying RyzenAdj licenses/notices are not supplied here, so this is not a
complete redistribution clearance; no source/binary is imported by this audit.

## 3. Candidate: oxp-tdpd at O pin

### Identity, coverage and bounds

**L3:** code labels its dispatch Strix Halo, family `0x1A`, model `0x70`; runtime construction checks the presence of
`mp1_smu_cmd`, probes PM-table availability/readability and loads defaults. It does **not** check DMI/CPUID against
Super X in that construction path; a readable table version is logged, not allow-listed. This is a Strix Halo
implementation reference for X2Mini PRO, not locally proven Super X detection.
(O:`tdpd/internal/tdp/tdp.go:22-42`, O:`tdpd/internal/tdp/tdp.go:103-135`,
O:`tdpd/internal/smu/smu.go:69-73`, O:`tdpd/main.go:76-110`.)

**L3:** input is uint32 watts, range checked at D-Bus and controller boundaries. The flat upstream 10–85 W range
is deliberate despite its source comment reporting a lower vendor battery ceiling; the D-Bus maximum is constant.
These values are **not our Super X envelope**, and the controller does not gate them by AC/battery state.
(O:`tdpd/internal/tdp/tdp.go:33-42`, O:`tdpd/internal/tdp/tdp.go:252-294`,
O:`tdpd/internal/dbusiface/tdplimit1.go:59-76`, O:`tdpd/internal/dbusiface/tdplimit1.go:119-130`.)

### Transport, units and policy

**L3:** hard dependency on `ryzen_smu` sysfs at `/sys/kernel/ryzen_smu_drv`; no libryzenadj invocation.
The process writes six little-endian u32 arguments to `smu_args`, a u32 command to `mp1_smu_cmd` or `rsmu_cmd`,
then reads response and arguments. STAPM/fast/slow use MP1 `0x14/0x15/0x16`, watts×1000 in the first argument;
STAPM failure triggers a second attempt via RSMU `0x31`, called PSMU in comments. This fallback occurs for any MP1
error, not just rejection. Its appropriateness on this unit remains unvalidated.
(O:`tdpd/internal/smu/smu.go:25-32`, O:`tdpd/internal/smu/smu.go:75-128`,
O:`tdpd/internal/tdp/tdp.go:22-31`, O:`tdpd/internal/tdp/tdp.go:217-225`,
O:`tdpd/internal/tdp/tdp.go:349-359`.)

**L3:** `all` writes STAPM=fast=slow=request; `headroom` writes STAPM=slow=request and fast=5/4 request capped at
MaxWatts; `stapm` restores captured fast/slow when available, otherwise changes STAPM only. STAPM is written first,
then fast, then slow; errors abort later writes but do not reverse earlier ones. An “applied” per-limit cache
means SMU accepted the command, not PM-table verified the resulting limit.
(O:`tdpd/internal/tdp/tdp.go:44-49`, O:`tdpd/internal/tdp/tdp.go:252-359`.)
**L5 measurements:** upstream reports prolonged package power well above a midrange STAPM-only request, while
setting all three limits bounded its test; a low STAPM-only test appeared to settle quickly. This motivates
separate STAPM/fast/slow semantics and multiple observation windows, not adopting that machine's settings or
thermal figures. (O:`docs/tdpd.md:49-80`.)

### PM-table read-back versus cached D-Bus intent

**L3:** status reads the actual exposed PM table; fields are LE float32 watts, at offsets 0/4 (STAPM limit/value),
8/12 (fast), 16/20 (slow). Reads serialize with mailbox writes in-process. The parser checks length and only
STAPM's plausibility (positive, non-NaN, ≤500); it does not establish the identity/layout or validate every field.
Offset validation claimed in comments is **L5 X2Mini measurement**, not Super X evidence.
(O:`tdpd/main.go:161-182`, O:`tdpd/internal/smu/pmtable.go:13-39`,
O:`tdpd/internal/smu/pmtable.go:65-103`.)

**L3:** construction tolerates absent/unreadable PM tables and continues with cache fallback. `Current()` rounds
and clamps observed STAPM to the advertised range, or returns LastApplied/minimum on failure. D-Bus initializes
from `Current()` but later `Set` stores/announces requested intent **before** asynchronous hardware work. Commits
use acknowledgement caches without a PM-table compare; failed commits correct the property to LastApplied, or
leave the optimistic value if there is no last success. After partial failure LastApplied need not describe all
three hardware limits. (O:`tdpd/internal/tdp/tdp.go:118-135`, O:`tdpd/internal/tdp/tdp.go:326-346`,
O:`tdpd/internal/tdp/tdp.go:362-399`, O:`tdpd/internal/dbusiface/tdplimit1.go:55-76`,
O:`tdpd/internal/dbusiface/tdplimit1.go:119-156`.)

**L3 correction to prose:** notes say PM table is consulted at startup and after resume, but inspected resume code
forces reapplication, then republishes LastApplied; it does not read the PM table on that route. Never label a
D-Bus Get or resume correction “hardware read-back.” PM-table reads themselves can issue an RSMU table-transfer
mailbox command according to transport comments, so observation also needs bounded rate/ownership; avoid probing
after a mailbox failure merely to explain that failure.
(O:`docs/tdpd.md:153-165`, O:`tdpd/internal/dbusiface/resume.go:55-60`,
O:`tdpd/internal/tdp/commit.go:196-208`, O:`tdpd/internal/tdp/tdp.go:402-415`,
O:`tdpd/internal/smu/smu.go:51-61`, O:`tdpd/internal/smu/pmtable.go:65-72`.)

### Privilege, D-Bus and competing writers

**L3:** system bus name `io.aletheia.OxpTdp1`, object `/io/aletheia/OxpTdp1`, interface
`com.steampowered.SteamOSManager1.TdpLimit1`; RW `TdpLimit` uint32 watts, RO constant `TdpLimitMin/Max` uint32.
Standard Properties Get/GetAll/Set and PropertiesChanged plus Introspect are exposed; no separate apply-result,
raw three-limit observation or restore method is present in that interface. The bus name is requested DoNotQueue,
rejecting a second daemon with the same name, but this is not a hardware lease.
(O:`tdpd/internal/dbusiface/tdplimit1.go:25-29`, O:`tdpd/internal/dbusiface/tdplimit1.go:59-99`,
O:`tdpd/internal/dbusiface/tdplimit1.go:187-226`.)

**L3:** root systemd service, restricted filesystem/network/capability surface, Restart=on-failure and a mailbox
path condition. Bus policy restricts name ownership to root but permits default-context Properties/interface
calls, including setters, for SteamOS's user proxy; there is no polkit check in the setter. SteamOS integration is
an optional consumer, not a requirement for our GTK client; it must not become our authorization boundary.
(O:`tdpd/contrib/oxp-tdpd.service:1-40`, O:`tdpd/contrib/io.aletheia.OxpTdp1.conf:17-35`,
O:`tdpd/internal/dbusiface/tdplimit1.go:119-130`, O:`packaging/oxp-tdpd-bin/PKGBUILD:28-31`.)

**L3:** one commit goroutine and process-local SMU mutex serialize its traffic, including PM reads. The one-shot
`--set` explicitly bypasses coordination with an existing daemon; no cross-process lock protects the shared
argument buffer. Resume replays prior applied intent. The inspected apply path controls three limits, with no
PPD EPP handoff. (O:`tdpd/internal/tdp/commit.go:46-70`, O:`tdpd/internal/smu/smu.go:51-62`,
O:`tdpd/main.go:104-110`, O:`tdpd/internal/dbusiface/resume.go:55-60`,
O:`tdpd/internal/tdp/tdp.go:252-359`.) **L5:** upstream explicitly warns not to combine it with another
RyzenAdj-based writer that reapplies on resume/game launch (O:`docs/ryzen-smu.md:151-153`). **Proposal:** exclude
HHD/other TDP writers and direct CLI access, preserve PPD's EPP ownership, and qualify both owners' transitions.
A second unique bus name would not protect the hardware from either process or amdgpu.

### Contention, timeout, wedge and restore

**L5 failure report:** bursts of slider writes were reported to race amdgpu and wedge the SMU for the rest of the
boot, with `amdgpu: SMU: No response msg_reg: f resp_reg: 0`. **L3 mitigation:** debounce 250 ms, maximum settle
1 s and minimum interval 150 ms; unchanged acknowledged values are skipped; busy response `0xFC` alone gets
10/25 ms retry delays. Unknown/rejected/failed codes and I/O/short responses become errors. Fewer commands are
not proof of kernel-level arbitration or safe recovery from a wedge.
(O:`docs/tdpd.md:130-152`, O:`tdpd/internal/tdp/commit.go:14-35`,
O:`tdpd/internal/tdp/tdp.go:212-241`, O:`tdpd/internal/tdp/tdp.go:326-346`,
O:`tdpd/internal/smu/smu.go:99-156`.)

**L3:** shutdown waits up to 2 s for a pending write to flush; Close's context bounds waiting, not the underlying
sysfs write. There is no per-write cancellation in transport; a kernel-blocked write is not contained by the
Go context. No firmware restoration occurs on stop; restart-on-failure is not a restore mechanism. Prose says
firmware restores at boot (**L5**, not demonstrated on Super X), not on daemon crash. These paths supply no
independent crash/wedge recovery proof. (O:`tdpd/main.go:132-158`, O:`tdpd/internal/tdp/commit.go:244-257`,
O:`tdpd/internal/smu/smu.go:91-128`, O:`tdpd/contrib/oxp-tdpd.service:12-16`, O:`docs/tdpd.md:166-171`.)

**L3:** captured defaults persist **only fast/slow**, rounded to whole watts, as JSON, with no BIOS/APU/table identity
or STAPM baseline. Existing values are accepted if positive. Missing PM table, capture or persistence failures
warn rather than block all-mode writes. Recapture removes the old record before capture; persistence is a direct
WriteFile, not an atomic replacement. `stapm` policy's fast/slow restoration is not a full transaction restore or
exit/crash rollback. **L5:** notes warn initial capture is valid only before other writes and must be refreshed
following firmware changes. (O:`tdpd/internal/tdp/tdp.go:51-57`, O:`tdpd/internal/tdp/tdp.go:138-209`,
O:`tdpd/internal/tdp/tdp.go:272-290`, O:`docs/tdpd.md:82-98`.)

### Ubuntu 24.04 / kernel 7.0.0-42 and licensing

**L3 inventory:** Go module specifies **1.26.5**, godbus v5.2.2 and go-systemd v22.7.0. Packaging supplied is Arch
PKGBUILD/binary plus systemd/D-Bus/module-load/config/SteamOS registration; source installer builds and enables the
service and restarts SteamOS services. It is not an Ubuntu package or a passive audit tool.
(O:`tdpd/go.mod:1-10`, O:`packaging/oxp-tdpd-bin/PKGBUILD:15-31`,
O:`packaging/oxp-tdpd-bin/PKGBUILD:50-80`, O:`tdpd/install-tdpd.sh:46-48`,
O:`tdpd/install-tdpd.sh:89-111`.) **L6 feasibility proposal:** a dedicated `.deb` without SteamOS integration is
plausible, but requires a suitable Go toolchain, dependency/source inventory, restricted bus policy and separately
reviewed module packaging; no build or ABI compatibility was tested on noble.

**L3 requirement / L5 external version reports:** daemon requires the amkillam `ryzen_smu` fork. Notes name PM-table
`0x64010C` support at `b0988849ddfd6701c67b8b485d79dbdb02c2bd3a` and Linux-7.2 cpuid build fix
`d2983668300dd2a598e5a7dc40e71ce0678cc270`; these are reported driver history, not inspected driver commits.
There is no verified exact DKMS version/build for Ubuntu `7.0.0-42`; a 7.2 build fix is not proof it is required on
7.0, and a table working on X2Mini does not identify this Super X's firmware table. Require an immutable module pin
with both correct family-1Ah SMN access (§1 lead) and the **locally observed** table layout/version before a later
build/load review. A floating AUR HEAD recommendation is insufficient.
(O:`tdpd/internal/smu/smu.go:131-140`, O:`docs/ryzen-smu.md:3-20`, O:`tdpd/internal/tdp/tdp.go:103-129`.)

**L3 license inventory:** daemon files declare GPL-2.0-only, copyright 2026 Jeff Hagadorn. Transport header says the
same author relicensed his Apache-2.0 z13ctl transport for this GPL-2.0-only repository; do not apply the prose's
older Apache shorthand to this file. Keep the pin, headers, change notices and GPLv2 text/source obligations if
copying or translating code/tests; distributed derived works need GPLv2-compatible terms and corresponding source
including build/install scripts. (O:`tdpd/main.go:1-2`, O:`tdpd/internal/smu/smu.go:1-12`,
O:`docs/tdpd.md:175-187`, O:`LICENSE:29-61`.) **Proposal:** retain factual/protocol provenance for independent design
reuse; do not assume a translation avoids source-license obligations. Review compatibility before combining
GPL-2.0-only code with P's GPL-3.0-or-later code; no combined-code approach or license clearance is proposed here.

## 4. Other candidates (bounded evidence only)

| Candidate | What this packet supports | What remains before consideration |
|---|---|---|
| RyzenAdj-direct | **L3:** P calls a locked 0.19.0 Rust wrapper, not a CLI adapter (P:`Cargo.lock:637-656`, P:`src/performance/gpu/amd/ryzenadj.rs:4-8`). **L5:** O documents RyzenAdj `5775fc3` behavior: module selection at drv_version ≥0.1.7, failure when PM files are missing; without module, writes reportedly worked while `/dev/mem` PM-table mapping failed (O:`docs/ryzen-smu.md:62-123`, O:`docs/ryzen-smu.md:155-155`). | **L6 unresolved:** no direct RyzenAdj source clone supplied; exact C dispatch, timeout, restore, current license/dependency tree and noble ABI are unaudited. Direct calls would still need the same identity, three-limit read-back, exclusive ownership and recovery proofs; reported CLI success is not verification. Do not use `iomem=relaxed` as a read-back shortcut (O:`docs/ryzen-smu.md:105-123`, L5). |
| AMD DPTCi / ALIB | **L5 supplied lead:** kernel RFC exposes ALIB power controls and is not in stock Ubuntu (§1 URL). No cloned implementation to audit. **L1:** local machine has no platform_profile/firmware-attributes interface despite loaded amd_pmf. | **L6 unresolved:** exact Super X support, ABI, units, limits, read-back, privilege/API, arbitration, restore and license/package requirements. Do not infer arbitrary watt control from PMF loaded or coarse profiles. Owner would need a separately pinned kernel/driver audit and boot rollback decision; no patch/install recommendation follows from an RFC. |

## 5. Comparison against the section-4 rubric

Cells summarize the cited evidence above; citations here preserve the candidate/commit boundary. “Unproved” blocks
selection, rather than granting permission to fill gaps with inferred values.

| Criterion | PowerStation | oxp-tdpd | RyzenAdj-direct | AMD DPTCi |
|---|---|---|---|---|
| Identity / Super X | L3 explicit Super X/395 tables; DRM query (P:`rootfs/usr/share/powerstation/platform/dmi_overrides_apu_database.toml:139-143`, P:`src/performance/gpu/drm.rs:105-125`) | L3 fixed Strix Halo IDs; construction only checks interface/table (O:`tdpd/internal/tdp/tdp.go:22-31`, O:`tdpd/internal/tdp/tdp.go:103-135`) | L5 X2Mini behavior report only (O:`docs/ryzen-smu.md:62-94`) | L5 RFC lead; L6 Super X unresolved |
| Transport / units | L3 lib calls, W→mW; underlying dispatch L6 unresolved (P:`src/performance/gpu/amd/ryzenadj.rs:286-349`, P:`Cargo.lock:637-656`) | L3 sysfs MP1 14/15/16, RSMU 31 fallback, mW (O:`tdpd/internal/tdp/tdp.go:22-31`, O:`tdpd/internal/tdp/tdp.go:222-224`, O:`tdpd/internal/tdp/tdp.go:349-359`) | L5 module/raw-memory report; no inspected C implementation (O:`docs/ryzen-smu.md:62-123`) | L5 ALIB lead; L6 ABI/units unresolved |
| Bounds / power semantics | L3 advertised bounds not enforced; STAPM plus retained boost, fast 1.25×slow (P:`src/performance/gpu/amd/ryzenadj.rs:286-351`) | L3 integer flat bounds, all/stapm/headroom; no AC clamp (O:`tdpd/internal/tdp/tdp.go:33-49`, O:`tdpd/internal/tdp/tdp.go:252-294`) | L6 owner adapter/bounds absent | L6 limits/semantics unresolved |
| Hardware observation | L3 refresh/getters, logged refresh failure; no three-limit post-write comparison (P:`src/performance/gpu/amd/ryzenadj.rs:100-115`, P:`src/performance/gpu/amd/ryzenadj.rs:185-211`, P:`src/performance/gpu/amd/ryzenadj.rs:286-351`) | L3 PM status yes, D-Bus intent/cache; tolerates missing table (O:`tdpd/main.go:161-182`, O:`tdpd/internal/dbusiface/tdplimit1.go:119-156`, O:`tdpd/internal/tdp/tdp.go:118-129`) | L5 table-dependent reads (O:`docs/ryzen-smu.md:62-76`); L6 local proof absent | L6 read-back unresolved |
| Privilege / API | L3 root-owned system bus, broad sender policy; multiple RW properties (P:`rootfs/usr/share/dbus-1/system.d/org.shadowblip.PowerStation.conf:5-12`, P:`src/performance/gpu/dbus/tdp.rs:32-138`) | L3 root-owned system bus, broad Properties access; queued uint32 property (O:`tdpd/contrib/io.aletheia.OxpTdp1.conf:17-35`, O:`tdpd/internal/dbusiface/tdplimit1.go:119-130`) | L6 no service boundary audited | L6 kernel access policy/API unaudited |
| PPD/HHD/other owner | L3 per-object mutex only in reviewed path; L6 coexistence unproved (P:`src/performance/gpu/dbus/tdp.rs:43-49`) | L3 process mutex only, CLI race acknowledged; L6 PPD/HHD coexistence unproved (O:`tdpd/main.go:104-110`, O:`tdpd/internal/smu/smu.go:51-62`) | L5 competing-writer warning (O:`docs/ryzen-smu.md:151-153`) | L6 arbitration unresolved |
| Failure / contention | L3 errors/partial writes, no deadline there; L6 library behavior unaudited (P:`src/performance/gpu/amd/ryzenadj.rs:286-351`) | L3 coalescing/busy retries, uncancellable sysfs; L5 wedge report (O:`tdpd/internal/tdp/commit.go:31-35`, O:`tdpd/internal/tdp/commit.go:244-257`, O:`docs/tdpd.md:132-145`) | L5 family-1Ah SMN wedge lead; L6 mitigation inclusion unproved | L6 failure semantics unresolved |
| Exit/crash defaults | L3 no restore in reviewed lifecycle; unproved (P:`src/main.rs:81-92`, P:`rootfs/usr/lib/systemd/system/powerstation.service:1-9`) | L3 explicitly no restore, fast/slow-only capture (O:`tdpd/main.go:141-158`, O:`tdpd/internal/tdp/tdp.go:51-57`) | L6 restore unaudited | L6 restore unaudited |
| Noble / 7.0.0-42 | L3 Rust/archive/RPM inventory; L6 Ubuntu/module compatibility unproved (P:`Cargo.toml:20-34`, P:`Makefile:90-112`) | L3 Go 1.26.5/Arch/module dependency; L6 exact Ubuntu DKMS build unproved (O:`tdpd/go.mod:1-10`, O:`packaging/oxp-tdpd-bin/PKGBUILD:23-31`) | L6 exact package/module unqualified | L5 not stock Ubuntu; L6 patch route unreviewed |
| Reuse license | L3 GPLv3+, dependency inventory incomplete (P:`Cargo.toml:1-6`, P:`Cargo.lock:637-656`) | L3 GPLv2-only, transport relicensed (O:`tdpd/internal/smu/smu.go:1-12`) | L6 supplied reports are not a C-source license inventory | L6 no implementation/license inspected |

## 6. Local validation packet required before selection

This mirrors [Loadout section 7](LOADOUT_AUDIT.md#7-acceptance-criteria--sx-core-002-and-fan-ownershiprecovery) for package power.
All items are required for selection/production qualification, and none is performed or authorized here.
Start with fake transport/table/bus fixtures; hardware steps need a separate explicit opt-in task and owner-approved
bounds, recovery plan and finite job budget. **No power increase may be paired with first-time fan validation.**
Keep existing firmware thermal protections and independently qualified cooling throughout.

1. **Identity and immutable inputs:** record redacted DMI, CPU family/model, BIOS/EC/SMU/PM-table version/layout,
   kernel/config, exact loaded module build/source and SMN-accessor fix, candidate/dependency pins and package hashes.
   Prove support for this unit, not a marketing-name or path-only match. Missing/ambiguous identity blocks writes.
2. **Read-only baseline:** capture all three actual limits/time constants when available, independent package-power
   telemetry and its units/domain/cadence, thermals/RPM, AC/battery state and active owners. Demonstrate plausible,
   fresh, finite PM data; preserve raw values before rounding/clamping. Missing table/refresh failure must become
   unknown/error, never cached “observed.” PM reads need the same bounded transport ownership as writes.
3. **Bounds and semantics:** owner approves a conservative tested envelope per power source, prerequisites and stop
   conditions from independent evidence. Reject wrong types, bool-as-number, nonfinite, overflow, out-of-range
   and inconsistent triples server-side. Show STAPM, slow and fast behavior separately over suitable observation
   windows; no upstream table/preset defines our limits. Align advertised range with every actual write route.
4. **Restore before acquisition:** capture complete pre-write state from a known firmware-owned baseline before
   any package-limit writer runs; bind persisted recovery data to firmware/APU identity, store atomically and fail
   closed on capture/persistence failure. Distinguish exact prior-state restore from firmware-default ownership.
   Demonstrate a locally usable, independently initiated restore/rollback route first; do not assume daemon restart
   or reboot reestablishes defaults without observation.
5. **Exclusive ownership / qualified EPP owner:** inventory HHD, PPD, SteamOS, profiles, timers, resume hooks and
   direct CLI writers. Assign one package-limit owner and block bypasses, including the original candidate's broad
   D-Bus setters. PPD 0.21 retains EPP ownership. Prove EPP/profile/AC changes do not overwrite limits or trigger
   hidden upward reapplication; preserve requested-versus-observed separation. A userspace lock does not arbitrate
   amdgpu/firmware mailbox traffic; document transport-level containment and abort on contention.
6. **Before → set → read-back:** use a modest owner-approved reversible first change, not max-first. Timestamp each
   raw requested triple, command acknowledgement and independently refreshed limit triple with tolerance/deadline;
   fail the operation on any mismatch. Read-back should occur at a safe bounded rate after successful transport,
   not as an uncontrolled diagnostic command after a wedge. Partial success is failed/partial, never success from
   a cached aggregate. No dependent write follows a failed prerequisite.
7. **Observed package-power correlation:** under a bounded repeatable ordinary workload, compare baseline/changed/
   restored independent package-power time series against all three limit observations and temperatures/RPM.
   Record averaging windows, sensor domain and workload limitations. Low idle draw cannot prove a ceiling; power
   correlation supplements limit read-back and cannot replace it. Abort before thermal/power stop conditions.
8. **Restore → read-back:** invalidate pending intent, contain/drain outstanding operations, restore the complete
   captured/default state through the qualified route, independently read back and observe subsequent power and
   firmware behavior. Repeat for normal release, client disconnect, service stop and partial failure; prove no
   stale request or timer can write after recovery. Restore errors revoke authorization visibly.
9. **Crash/restart/resume:** fake faults first, then supervised owner-approved cases for daemon exception, SIGKILL,
   hung I/O/normal loop, bus loss, suspend/resume and restart. Prove an independent supervisor can restore/verify
   within a safe recorded deadline, without replaying stale intent. A timeout must contain late writes and owned
   descendants; an uninterruptible kernel transaction needs a demonstrated fallback or fails the gate. Do not
   deliberately reproduce an uncontrolled hardware wedge to satisfy a test.
10. **Failure and access tests:** use fakes for busy/rejected/unknown responses, denied/short I/O, malformed or stale
    PM tables, refresh failure, partial triples, persisted-state corruption, duplicate owners and burst requests.
    Check bounded output/runtime, serialization, cancellation generations, error reporting and bus authorization.
    Desired, queued, acknowledged, independently observed and restored states must remain distinguishable.
11. **Packet and separate authorization:** retain per-step pass/fail, UTC and monotonic timestamps, identities/pins,
    owner/lease, explicit bounds, before/set/read-back/restore raw units, power/thermal traces, freshness/tolerance,
    deadlines and stop/recovery initiator/results, post-recovery window, bounded logs and reviewer. Redact unique
    identifiers by default. Record aborts and unproved recovery as failures. Only a reviewed passing scope may
    advance capability status and a later policy authorization; a single manual pass authorizes no curves,
    startup replay, burst policy or higher-power operation.

## 7. Ranked proposal for the owner (no backend selected)

Selection rule: **the narrowest maintained interface that proves identity, bounds, observation, exclusive ownership
and restore**. Reject any candidate missing one of those proofs; keep the existing read-only target until the gate
passes. The ranking below is an order of further audit/qualification investment, not installation approval.

1. **PowerStation service first for further audit**, conditional on obtaining its exact locked lower-library/driver
   sources and resolving range enforcement, fresh three-limit observation, bus restrictions and independent restore.
   It offers the closest existing service/identity boundary, but its broad writable surface and STAPM/boost model
   need narrowing (P:`src/performance/gpu/dbus/tdp.rs:32-138`,
   P:`src/performance/gpu/amd/ryzenadj.rs:286-351`,
   P:`rootfs/usr/share/powerstation/platform/dmi_overrides_apu_database.toml:139-143`, L3).
   Prefer an upstream improvement plus a narrow ServiceClient/service adapter over
   a code transplant; retain our authorization and PPD ownership. If transport or recovery cannot be proved, reject
   it rather than treating issue closure as acceptance.
2. **oxp-tdpd as the next service candidate and the strongest inspected transport/qualification reference**, subject
   to exact Super X identity/table/module proof, observed-state API, restricted access, complete recovery records,
   cross-process ownership and independent restoration. Its current cache-first API/no-exit-restore policy fails our
   gate; debounce reduces traffic but does not prove arbitration
   (O:`tdpd/internal/dbusiface/tdplimit1.go:119-156`, O:`tdpd/main.go:141-158`,
   O:`tdpd/internal/tdp/commit.go:14-35`, L3). Borrow scenarios independently;
   do not inherit X2Mini watts, Steam dependencies or a second active daemon.
3. **RyzenAdj-direct only if a service cannot be narrowed sufficiently.** First obtain the exact C source and
   transport/license inventory; this option would put observation, ownership, packaging and recovery responsibility
   in our adapter (L6 proposed future work; evidence limits in §4). Avoid creating another raw mailbox stack solely
   because a CLI setter reports success.
4. **DPTCi as a future kernel-interface contender**, not an immediate noble implementation. A locally supported,
   maintained semantic kernel ABI that proves the full rule could outrank userspace mailbox approaches later;
   current RFC-only evidence does not do so (L5/L6, §4). Do not expand this audit into a kernel port or protocol RE.

Owner decisions required for the **next separately authorized task**, after the missing source audit is concrete:

- Choose whether to fund/review a restricted external service integration or adapter work; choose the exact
  candidate/dependency/module source pins and license distribution plan. No backend is selected by this document.
- Approve any root package install/module load, Secure Boot signing/enrollment if applicable, and a rollback boot
  entry/package removal route. Exact DKMS build/load compatibility on `7.0.0-42` is outstanding, not a reason to
  assume a newer kernel or install a floating driver. No `iomem=relaxed` workaround is proposed.
- Assign exclusive package-limit ownership and review narrowed D-Bus/polkit policy; retain PPD as EPP owner.
  Approve a supervised local packet with bounded workload/log/disk/runtime allocation, conservative evidence-based
  bounds, cooling prerequisites and independently usable recovery. Root access alone grants none of these proofs.
- After review, decide whether to select/reject/defer a candidate and separately authorize only the proven scope.
  This audit neither recommends Super X wattage limits nor closes SX-CORE-004's production-selection gate.

## 8. Validation and handoff

Only `docs/TDP_BACKEND_AUDIT.md` is changed. Reviewed pinned source ranges, reconciled documentation versus code
(in particular resume/read-back), checked citation paths/ranges and reviewed the diff for scope/whitespace.
No tests need to run for this inert docs-only change; unittest was **not run**, so there is no new unittest summary
or current-head gameplay evidence to report. No upstream execution, installation, root/hardware action or commit.
Outstanding: locked lower-library/driver audit, Ubuntu packaging/license closure, owner choice, and every local
qualification/recovery item in §6. Coordinator owns roadmap/ownership-document updates at integration.
