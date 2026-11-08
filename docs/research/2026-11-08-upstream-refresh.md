# Upstream research refresh — 2026-11-08

**Source:** Codex sub-agent (`codex exec`, read-only, web search) briefed from AGENTS.md, ROADMAP.md,
UPSTREAM_OWNERSHIP.md, LOADOUT_AUDIT.md, FROST_BAY.md and MINI_SSD.md. Evidence levels are the agent's;
items marked **[verified]** were re-checked the same day by the reviewing session (raw kernel source, GitHub API,
Ubuntu mainline index). Everything else is L3/L5 pending audit. Nothing here authorizes a local write.

Verified on 2026-11-08:

- `drivers/platform/x86/oxpec.c` at tag v7.2 contains `DMI_EXACT_MATCH(DMI_BOARD_NAME, "ONEXPLAYER SUPER X")`; v7.1 does not. The installed Ubuntu noble HWE kernel is 7.0.0-42 (no newer candidate), so the quirk is not reachable through stock packages yet. [verified]
- Ubuntu mainline builds publish `linux-image-unsigned-7.3.3-070303-generic_..._amd64.deb` (built 2026-11-06). [verified]
- ShadowBlip/PowerStation latest release is v0.9.0 (2026-11-01); issue #43 (Strix Halo TDP unavailable, GPU misclassified, old vendored RyzenAdj) was closed 2026-08-28. [verified]
- hhd-dev/hhd PRs #321 and #336 (Frost Bay) are still OPEN (last update 2026-10-16); issue #329 (Super X EC/battery/turbo report) is OPEN. [verified]
- srsholmes/onexplayer-apex-bazzite-fixes PR #20 (Super X oxpec DKMS) is OPEN since 2026-06-11. [verified]
- dahui/onexplayer-x2-mini-pro-cachyos ships `oxp-tdpd` (Go daemon, MP1 mailbox via `ryzen_smu` sysfs, PM-table read-back) and an `oxpec` DKMS package. [verified existence; behavior not audited]

---

Research checked **2026-11-08**, after reading the requested repository baseline. **PowerStation is the strongest new reuse candidate.** Ubuntu mainline builds offer a kernel-validation route; no public breakthrough resolves the Mini SSD failure. Nothing below establishes local write authorization.

**1. Internal fan / EC**

| Project/source | URL | Date | What it offers | Evidence level | Recommended action for Super X Helper |
|---|---|---|---|---|---|
| Linux / Ubuntu mainline | [7.2 source](https://raw.githubusercontent.com/torvalds/linux/v7.2/drivers/platform/x86/oxpec.c), [Ubuntu 7.3.3 build](https://kernel.ubuntu.com/mainline/v7.3.3/) | Aug–Nov 2026 | Super X mapping is present in 7.2. Ubuntu publishes 7.3.3 amd64 image/modules/headers; build succeeded, self-tests failed. **Noble HWE/OEM inclusion remains unverified**; Launchpad access was blocked. | L2 | **Audit:** concrete mainline test candidate, not a qualified daily-driver recommendation. Verify packaged module configuration/alias before booting. |
| Stable backport | [6.18 AUTOSEL submission](https://lists.openwall.net/linux-kernel/2026/08/31/2777) | Aug 31 | Super X quirk nominated for 6.18 stable. Submission alone does not prove a particular Ubuntu package contains it. | L2 | **Monitor:** inspect exact distro source rather than infer from version family. |
| Out-of-tree oxpec | [X2 Mini Pro repository](https://github.com/dahui/onexplayer-x2-mini-pro-cachyos), [Super X PR](https://github.com/srsholmes/onexplayer-apex-bazzite-fixes/pull/20) | Checked Nov 8 | Actual `oxpec-x2mini-dkms` packaging exists; Super X PR remains open. No maintained Ubuntu-specific Super X DKMS package verified. | L3 | **Audit:** packaging reference only; preserve upstream Super X mapping. |
| Subsequent oxpec work | [Apex charge fix](https://lkml.iu.edu/2609.2/11794.html), [Super X tablet-mode series](https://lists.openwall.net/linux-kernel/2026/07/28/796) | Jul 28; Sep 20 | Apex requires different charge registers. Super X tablet-mode proposal preserves existing G1 AMD behavior while separating its identity. No new confirmed `oxp_g1_a` fan/charge regression found. | L2 | **Monitor:** never transplant Apex charge semantics; tablet-mode work may save future rotation/keyboard-detection work. |

**2. Strix Halo APU/TDP**

| Project/source | URL | Date | What it offers | Evidence level | Recommended action for Super X Helper |
|---|---|---|---|---|---|
| PowerStation | [Releases](https://github.com/ShadowBlip/PowerStation/releases), [hardware report](https://github.com/ShadowBlip/PowerStation/issues/43) | **Sep 28–Nov 1** | v0.8.2 adds MAX+395, fixes integrated-GPU detection, updates libryzenadj to 0.19.0, and adds handheld overrides. Reporter demonstrated D-Bus writes with STAPM/PPT read-back on Strix Halo. | L3 implementation; L5 hardware report | **Audit first:** potentially reuse its UI-independent service instead of writing another RyzenAdj adapter. Super X limits remain unqualified. |
| RyzenAdj / `ryzen_smu` | [RyzenAdj releases](https://github.com/FlyGoat/RyzenAdj/releases?after=v0.6), [SMU issue #27](https://github.com/amkillam/ryzen_smu/issues/27) | Support predates refresh; Jul 25/Oct 1 updates | Strix Halo support exists. A Z13 investigation reports incorrect family-1Ah SMN access through C4/C8, corrected using kernel `amd_smn_*` accessors; reported failures include wedged GPU power management. | L3 support; L5 diagnosis | **Audit:** pin exact module/build and firmware-table support. “Strix Halo supported” does not establish safe transport or readable limits. |
| `oxp-tdpd` | [Implementation notes](https://raw.githubusercontent.com/dahui/onexplayer-x2-mini-pro-cachyos/main/docs/tdpd.md) | Sep 26 verification; current notes | X2 Mini Pro implementation reads PM-table limits, distinguishes STAPM targets from fast/slow ceilings, and coalesces writes after reported mailbox contention. D-Bus getters can return cached intent. | L3 implementation; L5 measurements | **Audit:** valuable qualification scenarios and transport reference. Do not inherit its battery ceiling or mistake cached properties for observation. |
| AMD DPTCi / HHD | [Kernel RFC](https://lkml.indiana.edu/2603.1/02794.html), [maintainer status](https://github.com/hhd-dev/hhd/pull/336#issuecomment-3210626509), [downstream tree](https://github.com/anatase-org/patchwork) | Mar; Aug 2026 | Kernel proposal exposes ALIB power controls plus platform profiles; HHD maintainer points to downstream Apex/X2 support. No current Super X DPTCi inclusion verified. | L2 proposal; L3 downstream | **Monitor/audit:** promising maintained kernel boundary, presently not evidence of stock Ubuntu Super X support. |
| PMF / platform profiles / TuxClocker | [Kernel ABI](https://docs.kernel.org/userspace-api/sysfs-platform_profile.html), [TuxClocker capabilities](https://github.com/Lurkki14/tuxclocker#currently-supported-devices-and-features) | Current | Platform profiles select policy, not exact watts or verified resulting limits. TuxClocker documents EPP/frequency/GPU controls, but no verified Super X package-TDP path was found. | L2/L3; exact-watt inference L6 | **Adopt** existing PPD ownership for profiles/EPP; **ignore** these as proof of arbitrary watt control. |

No material post-October-18 Loadout TDP development was verified.

**3. Frost Bay**

| Project/source | URL | Date | What it offers | Evidence level | Recommended action for Super X Helper |
|---|---|---|---|---|---|
| HHD / tbitu refresh | [#321](https://github.com/hhd-dev/hhd/pull/321), [#336](https://github.com/hhd-dev/hhd/pull/336), [protocol repository](https://github.com/tbitu/onexplayer-frostbay-bluetooth) | Checked Nov 8 | **Nothing materially new verified since September 22:** both PRs remain open; no merged plugin or new reimplementation established. | L3 | **Monitor:** retain local transport/health validation plan. |
| BlueZ Frost Bay issue | [#2155](https://github.com/bluez/bluez/issues/2155), [PHY proposal #2153](https://github.com/bluez/bluez/pull/2153) | May–Jul 2026 | Specific incomplete-GATT report concerns **Intel AX210**, with CSR dongle success. Proposed LE-1M workaround was closed; issue stale-closed, not demonstrated fixed. No MT7925-specific Frost Bay GATT fix found. | L5 report; L3 proposed code | **Audit:** useful diagnostic lead if reproduced; do not label Super X’s MT7925 faulty from Apex evidence. |

**4. BIWIN Mini SSD**

| Project/source | URL | Date | What it offers | Evidence level | Recommended action for Super X Helper |
|---|---|---|---|---|---|
| Linux NVMe driver | [Current PCI driver](https://raw.githubusercontent.com/torvalds/linux/master/drivers/nvme/host/pci.c) | Checked Nov 8 | No literal `1dee` PCI quirk entry found. Generic all-ones-CSTS diagnostics still suggest investigating power saving. No CL100-specific fix or matching public BAR-reset root cause found. | L2; CL100 attribution L6 | **Monitor:** continue existing APST experiment; ASPM remains a separate hypothesis, not a proven mitigation. |
| BIWIN firmware tooling | [Official Intelligence page](https://www.biwintech.com/biwin-intelligence/) | Current v5.0.0.1 | CL100 is listed; firmware updating is supported by the Windows-only utility. No public CL100 firmware changelog or disappearance fix identified. | L2 | **Monitor:** request model/firmware-specific release information; utility availability is not evidence of a fix. |
| Other BIWIN failures | [OneXPlayer 3 investigation](https://github.com/ZeroSegFault/CachyOS-OneXPlayer3/blob/main/docs/research/2026-10-07-onexplayer3-device-support.md), [Raspberry Pi #7551](https://github.com/raspberrypi/linux/issues/7551) | Aug–Oct 2026 | Reports involve `1dee:1602` resume failure and `1dee:5216` corruption, respectively—not CL100 `2268` spontaneous configuration loss. | L5 | **Ignore as direct fixes:** retain as comparators. No matching Super X/Apex/Super V/AYANEO breakthrough found. |

**5. Battery, RGB and controllers**

| Project/source | URL | Date | What it offers | Evidence level | Recommended action for Super X Helper |
|---|---|---|---|---|---|
| Super X HHD report | [#329](https://github.com/hhd-dev/hhd/issues/329) | Jun 21–26 | Reports working charge limit/bypass and fan controls with patches; identifies Turbo as Ctrl+Meta+Alt. Maintainer says HHD lacked chord support. Suggested board mapping differs from accepted upstream mapping. | L5 | **Audit:** battery qualification can accompany oxpec bring-up; test hotkey chord explicitly. Prefer accepted kernel mapping. |
| Kernel `hid-oxp` | [Driver](https://raw.githubusercontent.com/torvalds/linux/master/drivers/hid/hid-oxp.c), [HHD device table](https://github.com/hhd-dev/hhd/blob/master/src/hhd/device/oxp/const.py) | Current | Kernel HID control provides another RGB/button-owner candidate. It matches USB identities/usage pages; model-family similarity is insufficient. No new Super X-specific OpenRGB or InputPlumber qualification verified. | L2/L3 | **Audit:** identify actual controller interfaces and existing owner before RGB work; retain external controller-stack strategy. |

**6. Service/UI designs worth borrowing**

| Project/source | URL | Date | What it offers | Evidence level | Recommended action for Super X Helper |
|---|---|---|---|---|---|
| PowerStation | [D-Bus interfaces](https://github.com/ShadowBlip/PowerStation#documentation) | Current | Documented UI-independent CPU/GPU service and interface XML. | L3 | **Audit:** strongest service-boundary reference; authorization, observed-state semantics and rollback still require review. |
| TLP Panel | [Repository](https://github.com/timemrah/tlp-panel) | Checked Nov 8 | Python GTK4/libadwaita panel, Ubuntu 24.04 packaging, capability-dependent controls, fixed validated privileged-helper verbs through polkit. | L3 | **Audit:** borrow panel/packaging and narrow-action patterns, without introducing competing TLP ownership. |
| Ryzenadj-gtk | [Repository](https://github.com/marleylinux/Ryzenadj-gtk) | Checked Nov 8 | Matching UI stack and profiles, but sudoers-based writes and persistent reapplication. No verified transactional rollback design found. | L3 | **Ignore** as privilege/transaction reference; optional visual inspiration only. |

**Plan impact**

- Put **PowerStation ≥0.8.2 and `oxp-tdpd` audit ahead of new SX-CORE-004 implementation**.
- Make **SX-CORE-002 kernel selection concrete**, then qualify fan recovery and battery interfaces together.
- Keep **SX-CORE-005 and SX-UI-009**: none of these projects establishes the required authorization/read-back/rollback contract.
- Preserve Frost Bay and SSD gates. The local APST log’s 60-day endpoint should read **2027-01-04**, not 2026-01-04; the simultaneous kernel upgrade remains a confound.