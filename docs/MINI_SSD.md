# Mini SSD — Reliability Investigation

## Objective

Determine why the removable 2 TB Mini SSD used with the ONEXPLAYER Super X can intermittently become undetected or unreliable, and establish an evidence-backed fix, mitigation, or hardware diagnosis before trusting it with important data.

Primary test device is expected to be a **BIWIN CL100 2 TB Mini SSD** or equivalent unit supplied for the Super X. Confirm the exact model/firmware locally before assuming this document's public-reference identity matches the installed device.

## Current public baseline

BIWIN documents the CL100 as:

- PCIe Gen4 x2;
- NVMe 1.4;
- capacities through 2 TB;
- DRAM-less;
- up to approximately 3.7 GB/s sequential read and 3.4 GB/s sequential write depending on capacity.

This is important because the Super X should expose a normal PCIe/NVMe failure chain that Linux can inspect rather than an opaque proprietary storage protocol.

Community reports across devices using the Mini SSD form factor describe intermittent detection, reseating/reboot sensitivity, and in some cases I/O failures despite superficially healthy SMART reports. Those reports are useful leads, not proof of the local root cause.

## Safety rule

**Do not store important or unique data on the test Mini SSD until the reliability qualification section passes.**

Default diagnostics are read-only.

## Failure model

Classify every observation into the highest layer still functioning:

```text
Physical / slot power / contact
        ↓
PCIe enumeration + link training
        ↓
NVMe controller
        ↓
NVMe namespace / block device
        ↓
I/O path
        ↓
filesystem / application
```

### States

#### ABSENT

No matching PCIe endpoint appears.

Investigate:

- seating/contact;
- slot power;
- link training;
- BIOS/firmware;
- PCIe hotplug assumptions;
- hardware fault.

#### PCIE_ONLY

PCIe endpoint remains visible but Linux does not expose a usable NVMe controller/namespace.

Investigate:

- controller reset/failure;
- NVMe driver interaction;
- power-state transitions;
- firmware;
- PCIe/AER errors.

#### NVME_PRESENT

Controller/namespace/block device are visible and no current I/O failure is known.

This is not automatically `HEALTHY`; reliability still needs qualification.

#### IO_DEGRADED

Device remains enumerated but I/O errors, timeouts, controller resets, corruption, or repeated filesystem failures occur.

Investigate controller, thermals, power state, media, and only then filesystem/application specifics.

#### HEALTHY

Device has passed the currently defined repeated reliability suite without link/controller/I/O errors.

## Baseline capture

When the drive is working, record:

```bash
lspci -nn
lspci -vv
nvme list
nvme id-ctrl /dev/nvmeX
nvme id-ns /dev/nvmeXn1
nvme smart-log /dev/nvmeX
journalctl -k
```

Also capture relevant sysfs information for:

- PCI vendor/device/subsystem IDs;
- negotiated link width/speed;
- ASPM/link-control state;
- runtime power-management state;
- NVMe firmware revision;
- NVMe supported power states;
- temperature and critical warnings.

Do not hard-code `/dev/nvmeX`; resolve the tested device by stable PCI/NVMe identity.

## Diagnostic snapshot schema

A future tool should record a structure conceptually like:

```json
{
  "timestamp": "...",
  "classification": "NVME_PRESENT",
  "pcie": {
    "present": true,
    "address": "...",
    "vendor_device": "...",
    "link_speed": "...",
    "link_width": "..."
  },
  "nvme": {
    "controller_present": true,
    "namespace_present": true,
    "firmware": "...",
    "temperature_c": 0,
    "critical_warning": 0
  },
  "kernel": {
    "aer_errors": [],
    "nvme_errors": []
  }
}
```

## Reproduction matrix

Run repeated cycles rather than one-offs.

| Test | Runs | PCIe | NVMe | I/O | Temp | Kernel errors | Result |
|---|---:|---|---|---|---|---|---|
| Cold boot | TBD | | | | | | |
| Warm reboot | TBD | | | | | | |
| 30 min idle | TBD | | | | | | |
| Suspend/resume | TBD | | | | | | |
| Sequential read | TBD | | | | | | |
| Disposable sequential write | TBD | | | | | | |
| Post-load idle | TBD | | | | | | |
| Thermal cooldown/retest | TBD | | | | | | |

Only add a test when its data is useful for discriminating a hypothesis.

## Root-cause hypotheses

### H1 — seating/contact sensitivity

**Why plausible:** community reports sometimes describe recovery after reseating/pushing the module more firmly.

**Evidence needed:** failures at PCIe enumeration level correlated with seating/cold-insertion behavior and unaffected by Linux software changes.

**Status:** HYPOTHESIS — not implicated by the two recorded recoveries (both were software remove/rescan or cold boot, not reseats), not excluded.

### H2 — PCIe power-management / ASPM transition

**Why plausible:** intermittent NVMe disappearance often warrants checking link power state, but no local evidence exists yet.

**Prediction:** endpoint/controller loss correlates with a specific idle/suspend transition and can be changed reproducibly by one targeted power-management experiment.

**Status:** HYPOTHESIS — local evidence (OBS-2026-08-29-01, OBS-2026-09-19-01) is consistent with H2/H3, but two of three losses happened under active I/O minutes after mounting, so a pure idle/deep-state trigger is not sufficient. Not yet discriminated from H3 or H6. ASPM L1.2 alone is ruled out by OBS-2026-11-18-01 (loss with L1.2 off).

### H3 — NVMe controller power state / firmware

**Prediction:** PCIe endpoint remains while controller resets/timeouts or namespace disappears; kernel logs show NVMe-level failure.

**Status:** HYPOTHESIS — local evidence (OBS-2026-08-29-01, OBS-2026-09-19-01) is consistent with H2/H3: every loss is the same signature (`CSTS=0xffffffff`, command register cleared, reset fails with `-19`). Not yet discriminated from H2 or H6. The APST form of H3 is ruled out by OBS-2026-11-15-01 (loss with APST off).

### H4 — thermal instability

**Why plausible:** very small high-performance storage has limited thermal mass and community reports mention high temperatures.

**Prediction:** failures correlate strongly with temperature/load, while cold/idle operation remains reliable; PCIe/NVMe errors appear near a repeatable thermal threshold.

**Status:** HYPOTHESIS — weakened by the idle loss (OBS-2026-09-19-01) but revived slightly by two losses under active I/O (OBS-2026-08-29-01). No temperature was captured at those events. Strongly weakened by OBS-2026-10-31-01: 42.9 °C, idle, one minute before the loss.

### H5 — filesystem/application issue

**Prediction:** PCIe and NVMe remain fully healthy, raw/block-level checks remain stable, and failures remain specific to filesystem/application behavior.

**Status:** REJECTED for the recorded events — ext4 was the victim, not the cause (I/O errors appear only after the controller read all-ones), and one loss happened with nothing mounted.

### H6 — defective local hardware

**Prediction:** failures persist across OS/kernel/config environments and follow the SSD or slot in a way inconsistent with software controls.

**Status:** HYPOTHESIS — four identical losses on one unit are also what a marginal device would look like, and OBS-2026-10-31-01 shows the endpoint losing its PCI configuration without host action.

## Experimental discipline

Do not test all of these at once:

- ASPM off;
- different kernel;
- different filesystem;
- reseat drive;
- new mount flags.

A successful result would be impossible to interpret.

Instead reproduce first, inspect the failure layer, and select one smallest experiment.

## Controlled write testing

Read-only tests come first.

If write testing is needed:

- use only disposable test data;
- ensure no important filesystem is being targeted;
- prefer file-level tests before raw-device tests;
- record checksums before/after;
- monitor temperature and kernel logs;
- stop on controller resets, I/O errors, or critical SMART warnings.

Raw destructive endurance testing is outside normal project scope.

## Reliability qualification before real use

The Mini SSD should not be called reliable merely because a mitigation boots successfully.

Define and pass a minimum suite such as:

- [ ] 20 cold boots without disappearance;
- [ ] 20 warm reboots;
- [ ] 20 suspend/resume cycles if suspend is part of normal use;
- [ ] extended idle test;
- [ ] sustained read test;
- [ ] controlled large disposable write + checksum readback;
- [ ] post-write idle and resume;
- [ ] no PCIe link resets/AER errors attributable to the device;
- [ ] no NVMe controller resets/timeouts;
- [ ] no uncorrected media/data-integrity errors;
- [ ] acceptable temperature behavior.

Exact counts can be adjusted once the failure frequency is known, but the qualification threshold must be decided before declaring success.

## Local evidence notes

Read-only facts gathered from the development Super X on 2026-10-18 (journal review, kernel `7.0.0-38-generic`, BIOS `V1.01`; counts corrected the same day by the cross-boot capture below, which reads all 25 retained boots instead of the 12 reviewed by hand). These constrain how the investigation must be instrumented:

- **Controller index is not stable.** Across the 25 boots retained in the journal (2026-08-08 → the current boot) the Mini SSD (`0000:c4:00.0`, `1dee:2268`) was `nvme0` in 15 boots and `nvme1` in 10. Any log parsing or tooling must resolve the controller by PCI address per boot, never by `nvmeN`.
- **AER is unavailable on this platform.** Firmware `_OSC` reports `platform does not support [SHPCHotplug AER LTR DPC]`. Absence of AER messages is therefore *not* evidence of a clean link; PCIe-layer faults will surface only as NVMe driver symptoms (all-ones register reads, reset failures).
- **Current power-management configuration** (unprivileged sysfs read): ASPM policy `default`; endpoint `l1_aspm=1`, `l1_1_aspm=1`, `l1_2_aspm=1`, `l1_1_pcipm=1`, `l1_2_pcipm=1`, `clkpm=1`, `d3cold_allowed=1`; `nvme_core.default_ps_max_latency_us=100000` (APST enabled with deep states permitted); controller quirk `simple_suspend`; sleep mode `s2idle`.
- **Usage context:** the Mini SSD carries a single ext4 partition that is not in `/etc/fstab`; it is mounted on demand through the desktop automounter (udisks) and was not mounted at review time. It is idle most of the time, but losses have occurred both idle and under active I/O (see experiment log).
- **Kernel command line** carries no `nvme_core`/`pcie_aspm` parameters as of 2026-11-02, so the grub edits attempted during the 2026-08-29 recovery are not in effect and the baseline above is the stock configuration. Cause: `/etc/default/grub` line 9 sets `pcie_aspm=off nvme_core.default_ps_max_latency_us=0`, then line 10 reassigns `GRUB_CMDLINE_LINUX_DEFAULT` without them. The `pcie_aspm=off` after line 10's closing quote only sets an unused shell variable. Neither mitigation ran on this unit before 2026-11-05. Simply deleting line 10 would change two variables at once. Since the 2026-11-05 boot the grub file carries only `nvme_core.default_ps_max_latency_us=0`, and it is on the running command line (EXP-2026-11-05-01). `pcie_aspm` is still stock.
- **Event frequency so far:** 3 controller losses in 2 of 25 boots / 71 days / 183 `PM: suspend entry` lines (2026-08-08 → 2026-10-18), all with the identical `CSTS=0xffffffff` → `reset failure: -19` signature. Two came within 7–14 minutes of mounting the drive and doing I/O; one came after 11 h idle. Reproduction by a bounded matrix is still unlikely at this rate; passive capture (now built, see Instrumentation) is the right first instrument, and mounting the drive for ordinary use is the most likely way to see the next event.

### Instrumentation

Passive, read-only capture added so the next drop-off arrives with context. Nothing here writes to the drive, mounts it, changes kernel parameters or starts nvme-cli.

**Cross-boot kernel events** (`superx-diag`, key `mini_ssd_events`):

- Lists every boot the journal retains, then reads that boot's kernel log with `journalctl -k -b <id>`. Plain `journalctl -k` without `-b` reads only the current boot; that is how the first hand review undercounted, so always pass a boot id when checking history by hand.
- Resolves the Mini SSD controller per boot from `nvme nvmeN: pci function 0000:c4:00.0`, so the `nvme0`/`nvme1` swap cannot misattribute internal-SSD messages. Lines addressed to `nvme 0000:c4:00.0:` are kept even when no controller ever probed, so a probe failure at boot (`Device not ready`, `Removing after probe failure`) is captured.
- Each boot records `pcie_enumerated` (the endpoint appeared on PCIe) and `nvme_probed` (the NVMe driver bound it). False/False means absent, True/False means PCIe only with no NVMe probe, True/True means probed.
- Keeps only Mini SSD-scoped lines (controller, PCI address, namespace or partition such as `nvme0n1p1`) that match: controller is down, Disabling device, reset, timeout, Device not ready, Removing after probe failure, I/O error, data loss, data will be lost, aborting journal, remounting filesystem read-only, failed to suspend, enabling device. Probe noise is dropped.
- Every event carries a `kind`: `loss` (controller is down, Disabling device, Device not ready, Removing after probe failure), `io_error` (I/O and ext4 damage lines), `aftermath` (failed to suspend), `recovery` (enabling device after a loss in the same boot) or `other`. Losses are counted as episodes: a `loss` line starts an episode unless one is already open, and only a fresh `pci function` probe closes it. The summary header reports loss episodes, not raw line counts, and always prints every `loss` line.
- Event timestamps are normalized to UTC, matching boot `start` and the sampler, so the three line up without conversion.
- Records the number of `PM: suspend entry` lines per boot and, for each event, how many suspends preceded it in that boot.
- Never emits the probe line carrying `subsysnqn`, which embeds the serial. Hostnames are dropped.
- After a loss, every later `s2idle` attempt in that boot logs `PM: failed to suspend async: error -16` for the dead endpoint (`aftermath`), and a manual remove/rescan logs `enabling device` (`recovery`). Those belong to one episode, not new losses. On other machines `enabling device` can be normal probe output, which is why it only counts as `recovery` after a loss.
- Reads the journal of every retained boot, so it stays a diagnostic action and is not part of UI refreshes. Reading the system journal needs `adm` or `systemd-journal` group membership (the development user is in `adm`); without it the section reports `unavailable` instead of silently returning zero events.

**Cheap per-refresh telemetry** (UI snapshot, `mini_ssd` observed value; also visible on the Storage page and dashboard card as e.g. `Gen4 x2 · 46.9 °C`):

- `link_speed`, `link_width`, `max_link_speed`, `max_link_width` from the PCI device's `current_link_*`/`max_link_*`. A current value below max is shown as `(max Gen4 x2)` and is worth recording.
- `aspm` (`l1`, `l1_1`, `l1_2`) from the PCI device's `link/` directory.
- `temperature_c` from the `nvme` hwmon whose `device` link resolves under the Mini SSD PCI device (unprivileged; SMART stays unavailable without root). This read is not passive: upstream, the nvme hwmon driver fetches the SMART log with an admin command, which wakes the drive. On 2026-10-31 a sample blocked for 63.5 s on the unresponsive controller, the only sample over 2 s in that boot.
- sysfs-only, so refreshes stay cheap, but see the temperature note above. The UI snapshot is not persisted, so the sampler below exists to keep a history.

**Periodic sampler** (`superx-mini-ssd-sample`, key `mini_ssd_telemetry_log` in `superx-diag`):

- One run = one JSON line appended to `$XDG_STATE_HOME/superx-helper/mini-ssd-telemetry.jsonl` (default `~/.local/state/superx-helper/`): `timestamp_utc`, `state` (`ABSENT`/`PCIE_ONLY`/`NVME_PRESENT`), `pci_address`, `controller`, `link_speed`, `link_width`, `max_link_*`, `aspm`, `temperature_c`, plus `power` (`l1_1_pcipm`, `l1_2_pcipm`, `clkpm`, `d3cold_allowed`, `runtime_status`: the remaining H2 variables) and `io` (`reads_completed`, `sectors_read`, `writes_completed`, `sectors_written` from `/sys/block/<ns>/stat`, and `mounted`). The I/O counters are cumulative since boot, so activity is the difference between consecutive samples; that is what separates the idle loss from the two under-I/O losses. `mounted` comes from `/proc/self/mountinfo` matched on `/dev/<ns>`; no mount point or other mount detail is stored. Same kind of sysfs reads as above; no journalctl, nvme-cli or mount, and the log is the only file written. The temperature read does reach the controller once per sample (see above). It keeps logging when the drive is absent. Rows also carry `controller_state`, the kernel's value from the controller's sysfs `state` (no drive access). `NVME_PRESENT` requires `live`, so a `dead` or `resetting` controller logs `PCIE_ONLY`; a single `PCIE_ONLY` row with `resetting` or `connecting` is a transition, not a loss. `namespace` and `mounted` are kept for a non-live controller. Rows written before 2026-11-02 have no `controller_state` and logged `NVME_PRESENT` even for a dead controller; in those, a null `temperature_c` is the marker of a loss (OBS-2026-10-31-01).
- The file is capped at the newest 50 000 lines (about 35 days at 60 s).
- `superx-diag` embeds the last 200 samples and prints a `Mini SSD Samples:` summary line (last sample time and values, or `no samples`).
- Manual run: `superx-mini-ssd-sample` (or `-o PATH` to write elsewhere). From a source checkout: `PYTHONPATH=src python3 -m superx_helper.mini_ssd_sampler`.
- Optional user timer (every 60 s, no root; units in `contrib/systemd/`). The install step is yours to run:

```bash
mkdir -p ~/.config/systemd/user
sed "s|@BIN@|$(command -v superx-mini-ssd-sample)|" contrib/systemd/superx-mini-ssd-sample.service > ~/.config/systemd/user/superx-mini-ssd-sample.service
cp contrib/systemd/superx-mini-ssd-sample.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now superx-mini-ssd-sample.timer
```

Remove with `systemctl --user disable --now superx-mini-ssd-sample.timer` and delete the two unit files. After pulling a newer unit, repeat the `sed`/`cp` and `daemon-reload` steps; the installed copy does not update itself.

- **Sandbox, and its limit on this unit.** The service sets `ProtectSystem=strict`, `ProtectHome=read-only`, `PrivateUsers=yes` and `StateDirectory=superx-helper`, so on a host that allows it only `~/.local/state/superx-helper` is writable. Tested on the development Super X on 2026-10-18 (Ubuntu, systemd 255, `kernel.apparmor_restrict_unprivileged_userns=1`): the user manager cannot create a mount namespace there, systemd skips these settings without an error, and a probe unit could still write outside the state directory. On this unit the "only the log is written" guarantee therefore rests on the sampler's code and tests, not on the sandbox.

- Reading a sample next to an event: take the event time from `mini_ssd_events` (both are UTC) and look at the last samples before it. Useful questions: was the drive mounted and were the `io` counters moving, did `link_speed`/`link_width` drop below `max_*` first, did ASPM or `power` states change, was `temperature_c` rising, and did `state` go `NVME_PRESENT` → `PCIE_ONLY`/`ABSENT` between two samples. Samples are 60 s apart, so the last one can predate the loss by up to a minute (and suspend gaps show as missing minutes, not as data). A sample is context, not proof of cause, and says nothing about reliability.

**Exporting evidence:**

```bash
superx-diag
superx-diag --json -o ~/superx-diag-$(date +%F).json
```

From a source checkout use `PYTHONPATH=src python3 -m superx_helper.collector` with the same flags. Attach the JSON to the experiment-log entry. Identifiers stay redacted unless `--include-identifiers` is passed.

This instrumentation adds evidence only. It does not change the reliability state (`NOT_QUALIFIED`) and does not tick any qualification item.

## Experiment log

### EXP-2026-11-17-01 — ASPM L1.2 disabled, APST restored (ended 2026-11-18: loss occurred)

**Question:** Does disabling ASPM L1.2 on the Mini SSD endpoint stop the controller losses?

**Baseline (boot started 2026-11-17 18:08 MST):**
- kernel: `7.0.0-43-generic`, up from `7.0.0-42-generic` in the loss boot of OBS-2026-11-15-01
- BIOS: `V1.01`
- power state: sleep mode `s2idle`; no suspend yet in this boot
- Frost Bay: not involved
- Mini SSD state: `live`, `nvme1` in this boot, Gen4 x2, no loss lines since boot. The drive was dead from the 2026-11-15 loss until the previous boot ended 2026-11-17 18:06, and enumerated normally without a reseat.
- other relevant config: `nvme_core.default_ps_max_latency_us=100000` (stock; the parameter is gone from `/etc/default/grub`, backup `/etc/default/grub.bak-2026-11-15`); ASPM policy `default`; endpoint `l1_aspm=1`, `l1_1_aspm=1`, `l1_1_pcipm=1`, `l1_2_pcipm=1`, `clkpm=1`, `d3cold_allowed=1`; per-minute sampler timer active

**Current hypothesis:** H2. The endpoint fails on an ASPM L1.2 exit and comes back with its PCI configuration reset.

**Prediction if hypothesis is true:** no `controller is down` / `reset failure: -19` episode during a run long enough to beat the baseline rate.

**Single variable changed:** `l1_2_aspm` = `0` on `0000:c4:00.0`, written as root to sysfs at 18:15:15 MST and read back as `0`. APST went back to stock in the same reboot, so relative to the previous boot two settings differ; relative to the stock configuration of the first four losses, only L1.2 does.

**Confounds:**
- The kernel update to `7.0.0-43` arrived in the same reboot. Losses span `-30`/`-31`, `-38` and `-42`, so a kernel fix is not a leading explanation, but a clean run cannot exclude it.
- The sysfs write does not survive a reboot. It must be repeated after every boot, and any time spent with `l1_2_aspm=1` (7 minutes in this boot) does not count toward the run. The sampler's `aspm.l1_2` field records the actual state per minute.
- `l1_2_pcipm` (PCI-PM L1.2) is left at `1`. It is a separate mechanism and is not the variable under test.

**Procedure:**
1. After every boot, write `0` to `link/l1_2_aspm` before mounting, and confirm the read-back.
2. Use the drive normally, including mounting it.
3. Leave APST, the other ASPM states, the sampler and the kernel command line unchanged.
4. Check `mini_ssd_events` and the sampler log periodically, including for Gen1 episodes and `genctr mismatch` lines.

**Stop and record if:** a loss episode occurs (record it as OBS with the sampler context), or another variable changes (kernel, BIOS, other ASPM states, slot or reseat).

**Pass bar:** 60 days without a loss episode with `l1_2_aspm=0` throughout, ending no earlier than 2027-01-16. Passing supports this mitigation but does not tick the reliability qualification. The drive stays `NOT_QUALIFIED`.

**Notes:**
- First mount after the 2026-11-15 journal abort, at 18:15:25 MST: `EXT4-fs (nvme1n1p1): recovery complete`, mounted r/w with no error lines. The filesystem holds 28K of data, so this says the journal replayed cleanly, not that data integrity was tested.

**Observed result:** a loss episode on 2026-11-18 11:40 MST, 17 h 25 min after the L1.2 write, with `l1_2_aspm=0` in every sample since 18:16 (OBS-2026-11-18-01). Prediction failed.

**Conclusion:** REJECTED for "ASPM L1.2 is required for the loss".

**Next smallest discriminating experiment:** see OBS-2026-11-18-01.

### OBS-2026-11-18-01 — Controller loss with ASPM L1.2 off, after three recovered resets (passive observation)

Reviewed 2026-11-18, read-only, with the controller still `dead`. Sixth loss episode, same signature.

**Baseline:** as EXP-2026-11-17-01. Kernel `7.0.0-43-generic`, APST stock (`100000`), `l1_2_aspm=0`, other ASPM states on, no suspend in this boot. ext4 mounted r/w since 2026-11-17 18:15; 1465 reads and 9 writes since boot; counters last moved at 18:16 on 2026-11-17, 17 h before the loss.

**Captured evidence (kernel log and sampler, 2026-11-18 MST):**

```text
03:23:46 request 0x0 genctr mismatch (got 0x0 expected 0xb); invalid id 0 completed on queue 0
03:24:48 opcode 0x2 (Admin Cmd) QID 0 timeout, reset controller   -> recovered, live
03:39:57 genctr mismatch (expected 0xe); invalid id 0             -> 03:40:58 timeout, reset, recovered
07:04:34 genctr mismatch (expected 0xc); invalid id 0             -> 07:05:38 timeout, reset, recovered
11:38:06 last normal sample: 40.9 °C, Gen4 x2, l1_2 off, live
11:40:04 controller is down; will reset: CSTS=0xffffffff, PCI_STATUS=0x10
11:40:04 enabling device (0000 -> 0002); Disabling device after reset failure: -19
11:40:04 EXT4-fs: shut down requested (2); Aborting journal; JBD2 I/O error on journal superblock
15:29    operator unmount; 16:24 mount attempt: unable to read superblock
```

Endpoint config space after the loss: `command=0x0000 cacheline=0x00 BAR0=0x00000004`, kernel BAR0 resource `0xd4a00000`. Link still reads Gen4 x2. Sampler, 1037 rows before the loss: all `live`, all Gen4 x2, 37.9–46.9 °C, four gaps of about 2 minutes, one at each event above.

**Spurious completions per retained boot (13 boots, journal back to 2026-09):**

| Boot | Kernel | Config | `genctr mismatch` | Losses |
|---|---|---|---|---|
| 2026-09-18 → 09-19 | `-31` | stock | 0 | 1 |
| 2026-10-20 → 11-05 | `-38` | stock | 0 | 1 |
| 2026-11-05 → 11-17 | `-42` | APST off | 1 | 1 |
| 2026-11-17 → | `-43` | L1.2 off | 3 in 17 h | 1 |

**Reading of the evidence:**
- ASPM L1.2 alone is not required, and APST alone is not required (OBS-2026-11-15-01). The two have never been off in the same boot, so "either deep state is enough" is not excluded. L1, L1.1 and clock PM were on in every loss.
- Each `genctr mismatch` lands on a sampler tick: the controller answers the sampler's Get Log Page with a completion for command id 0, which the driver did not issue, and the real command then times out. That is what a controller that restarted its admin queue state would do. Inference: the recovered events and the losses may be one fault, an internal controller restart, that sometimes also clears the PCI configuration. Not proven.
- The fault is getting more frequent: about one loss every 3–4 weeks through October, then four events in 17 hours of live time. The kernel changed in each of the last two boots, so a driver change that only makes the events visible, or more likely, is not excluded. A drive that is degrading (H6) fits the trend best.
- All four events happened on an idle, mounted filesystem with no host I/O. The sampler's once-a-minute admin read is the only regular traffic and is also what detects every event, so it cannot be separated from the trigger with this data. The 2026-08-29 and 2026-09-19 losses predate the sampler, so it is not required.
- Temperature unremarkable, no suspend involved, no link-speed change in this boot.
- Data: second journal abort on a filesystem holding 28K, no writes pending. Unverified until the next mount.

**What this rules out / weakens:** ASPM L1.2 alone ruled out. H4 stays weak, H5 rejected. H6 strengthened. H2 survives only as "any link low-power state" or in combination with APST.

**Conclusion:** HYPOTHESIS. Failure layer unchanged. Two single-variable host power experiments have failed; the cause is unresolved. The drive stays `NOT_QUALIFIED`.

**Next smallest discriminating experiment:** one run with all host-controlled power saving off for this drive: `nvme_core.default_ps_max_latency_us=0` plus every `link/*` ASPM and clock PM attribute at `0` (read back; `pcie_aspm=off` is not enough, it leaves firmware-set ASPM in place). At the current event rate a few days is a meaningful run. A loss or `genctr mismatch` in that state takes host power management out and leaves H6/H1: reseat, then a second unit or vendor return. A clean run says power saving is involved and the states can be re-enabled one at a time. Separately, the sampler's temperature read could be turned off for a run to test whether admin traffic is the trigger.

### EXP-2026-11-05-01 — APST disabled (ended 2026-11-15: loss occurred)

**Question:** Does disabling NVMe autonomous power state transitions (APST) stop the controller losses?

**Baseline (boot started 2026-11-05 16:18 MST):**
- kernel: `7.0.0-42-generic`, up from `7.0.0-38-generic` in the loss boot of OBS-2026-10-31-01
- BIOS: `V1.01`
- power state: sleep mode `s2idle`; no suspend yet in this boot
- Frost Bay: not involved
- Mini SSD state: `live`, `nvme1` in this boot, Gen4 x2, no loss lines since boot; not mounted (see note below)
- other relevant config: ASPM policy `default`, endpoint `l1_aspm`/`l1_1_aspm`/`l1_2_aspm`/`clkpm` all `1`; per-minute sampler timer active

**Current hypothesis:** H3. The controller fails on an APST deep-state exit and resets its own PCI configuration (OBS-2026-10-31-01).

**Prediction if hypothesis is true:** no `controller is down` / `reset failure: -19` episode during a run long enough to beat the baseline rate.

**Single variable changed:** `nvme_core.default_ps_max_latency_us=0` (was `100000`). It is set in `/etc/default/grub`; the backup is `/etc/default/grub.bak-2026-11-02`. Confirmed on `/proc/cmdline` and in `/sys/module/nvme_core/parameters/default_ps_max_latency_us` = `0`. The parameter is global, so the internal KIOXIA also runs without APST.

**Confound:** the kernel update to `7.0.0-42` arrived in the same reboot, so a clean run supports "APST off or kernel -42". It is not attributable to APST alone. The earlier losses span `7.0.0-31` (OBS-2026-09-19-01) and `7.0.0-38` (OBS-2026-10-31-01), so a kernel regression was never a leading explanation.

**Procedure:**
1. Use the drive normally, including mounting it. Mounting is how two of the four losses were seen.
2. Leave ASPM, the sampler and the kernel command line otherwise unchanged.
3. Check `mini_ssd_events` (`superx-diag`) and the sampler log periodically.

**Stop and record if:** a loss episode occurs (record it as OBS with the sampler context), or another variable changes (kernel, BIOS, ASPM, slot or reseat).

**Pass bar:** 60 days without a loss episode, ending no earlier than 2027-01-04. At the observed rate of about one episode every 3–4 weeks, a gap that long by chance is about 10% likely. Passing supports this mitigation but does not tick the reliability qualification. The drive stays `NOT_QUALIFIED`.

**Notes:**
- The drive was dead from the 2026-10-31 17:43 loss until that boot ended on 2026-11-05 06:09. The next boot enumerated it normally without a reseat, as after every earlier loss.
- Not auto-mounted after boot: udisks marks the drive `HintSystem=true`, `HintAuto=false` (internal NVMe, not removable), so it must be mounted from Files or `udisksctl mount`. That is how it has always behaved, not a symptom of failure.
- Until the installed helper is reinstalled from `main` (after #26), sampler rows still lack `controller_state` and log a dead controller as `NVME_PRESENT`; a null `temperature_c` remains the loss marker for those rows.

**Observed result:** a loss episode on 2026-11-15 12:45 MST, 9 d 20 h into the boot, with the parameter still `0` (OBS-2026-11-15-01). Prediction failed.

**Conclusion:** REJECTED for "APST transitions are required for the loss". Caveat: `default_ps_max_latency_us=0` was confirmed in the module parameter, but the drive's APST feature was not read back (`nvme get-feature` needs root), so this rests on upstream driver behavior.

**Next smallest discriminating experiment:** restore `100000` and test ASPM L1.2 alone, as planned. Not started.

### OBS-2026-11-15-01 — Controller loss with APST off, mounted and idle (passive observation)

Reviewed 2026-11-15, read-only, with the controller still `dead`. Fifth loss episode, same signature as the other four.

**Baseline:**
- kernel `7.0.0-42-generic`, BIOS `V1.01`, boot started 2026-11-05 16:18 MST, Mini SSD `nvme1`
- `nvme_core.default_ps_max_latency_us=0`; ASPM policy `default`, endpoint L1/L1.1/L1.2 and `clkpm` enabled, `d3cold_allowed=1`
- two suspends in this boot; last resume 2026-11-08 06:57 MST, 7 d 6 h before the loss
- ext4 mounted r/w since 2026-11-05 16:29; 1824 reads and 39 writes since boot; counters last moved 2026-11-10 21:18 MST, 4.6 days before the loss
- Frost Bay: not involved

**Captured evidence (kernel log and sampler, 2026-11-15 MST):**

```text
12:43:26 last normal sample: 44.9 °C, Gen4 x2, L1/L1.1/L1.2 enabled, runtime active, live
12:44:26 next sample starts, then blocks about 64 s on the temperature read
12:45:30 nvme nvme1: controller is down; will reset: CSTS=0xffffffff, PCI_STATUS=0x10
12:45:30 nvme 0000:c4:00.0: enabling device (0000 -> 0002)
12:45:30 nvme nvme1: Disabling device after reset failure: -19
12:45:30 EXT4-fs (nvme1n1p1): shut down requested (2); Aborting journal
12:45:30 Buffer I/O error on dev nvme1n1p1, lost sync page write; JBD2: I/O error when updating journal superblock
later    EXT4-fs warning: error -5 reading directory block (every access to the mount point)
```

Endpoint config space after the loss: `command=0x0002 cacheline=0x00 BAR0=0x00000004`; kernel BAR0 resource still `0xd4a00000`. Same as OBS-2026-10-31-01: the endpoint is back at power-on defaults. Link still reads Gen4 x2.

**Two earlier anomalies in the same boot (new):**
- 2026-11-05 22:58:25 `request 0x0 genctr mismatch (got 0x0 expected 0x4)` and `invalid id 0 completed on queue 0`, then at 22:59:29 `opcode 0x2 (Admin Cmd) QID 0 timeout, reset controller`. The reset succeeded and the controller stayed `live`. The sampler shows one 2-minute gap there. First recorded case of this drive misbehaving and recovering. Opcode 0x2 is Get Log Page, which is what the sampler's temperature read issues.
- 2026-11-06 04:22–06:10 MST: 108 consecutive samples at `2.5 GT/s` x2 against a `16.0 GT/s` maximum, controller `live`. It ended with the 06:11 suspend; the link was Gen4 after resume and for the rest of the boot. First observed link-speed degradation (none in 17 851 earlier samples). Nothing in the kernel log marks the retrain.

**Reading of the evidence:**
- APST deep-state exit is not the cause. H3 in its APST form is out; a firmware fault unrelated to APST is not.
- The drive stopped answering between 12:43:26 and 12:44:26, with no host I/O for 4.6 days and no suspend for a week. The only traffic was the once-a-minute admin read and udisks housekeeping.
- A spurious completion, a silent drop to Gen1 and a config-space reset in one boot are three different symptoms of the endpoint or its link/power misbehaving. That moves weight toward H6 (marginal device) and the power/contact form of H1, and keeps H2 (ASPM) open. It does not separate them.
- Temperature unremarkable: 44.9 °C, range 37.9–53.9 °C over 12 862 samples in this boot.
- AER is unavailable on this platform, so there is still no direct PCIe error evidence.
- Data: the journal was aborted on an idle filesystem. No writes were pending for days, so loss is unlikely but unverified until the next mount replays or checks the journal.

**What this rules out / weakens:** APST ruled out. H4 stays weak, H5 rejected. H2, H6 and H1 (power/contact) remain.

**Conclusion:** HYPOTHESIS. Failure layer unchanged: endpoint loses its PCI configuration without host action. Cause unresolved. The drive stays `NOT_QUALIFIED`.

**Next smallest discriminating experiment:** after a reboot, restore `nvme_core.default_ps_max_latency_us=100000` and disable ASPM L1.2 alone for this endpoint. Watch the sampler for further Gen1 episodes and `genctr mismatch` lines, which may be earlier and more frequent markers than a full loss.

### OBS-2026-10-31-01 — Controller loss while unmounted, first event with telemetry (passive observation)

Reviewed 2026-11-02. Not a designed experiment. Same signature as the three earlier losses; first one with samples leading up to it.

**Baseline:**
- kernel `7.0.0-38-generic`, BIOS `V1.01`, boot started 2026-10-20 10:01 MST, Mini SSD `nvme0`
- last resume 06:53:54 MST, so about 10 h 50 min after the last suspend
- not mounted at any point in this boot; 226 reads and 0 writes since boot, and the counters did not move before the loss
- stock power configuration: the grub edits are not in effect (see Local evidence notes)
- Frost Bay: not involved

**Captured evidence (kernel log, 2026-10-31 MST):**

```text
17:41:34.86 last normal sample finishes (about 0.1 s): 42.9 °C, Gen4 x2, ASPM L1/L1.1/L1.2 enabled, runtime active
17:42:35.76 next sample starts, then blocks for 63.5 s (the only sample over 2 s in this boot)
17:43:39.18 nvme nvme0: controller is down; will reset: CSTS=0xffffffff, PCI_STATUS=0x10
17:43:39.19 udisksd: housekeeping error: NVMe Identify Controller: Interrupted system call
17:43:39.21 nvme 0000:c4:00.0: enabling device (0000 -> 0002)
17:43:39.21 nvme nvme0: Disabling device after reset failure: -19
20:09-20:11 six s2idle attempts abort: nvme 0000:c4:00.0: PM: failed to suspend async: error -16
later       nvme nvme0: Identify namespace failed (-5), three times, aftermath of periodic scans
```

Read 2026-11-02 from the endpoint's config space (first 64 bytes of sysfs `config`, unprivileged), with the controller `state` = `dead`:

```text
endpoint   command=0x0000 cacheline=0x00 BAR0=0x00000004
kernel     BAR0 resource = 0xd4a00000
KIOXIA     command=0x0406 cacheline=0x10 BAR0=0xd4b00004 (healthy comparison)
```

**Reading of the evidence:**
- The endpoint's BAR0 and cache line size are back at power-on defaults while the kernel still believes the old address. Nothing in the log shows the host resetting it. The drive lost its PCI configuration on its own: a firmware self-reset, a slot power glitch or a link-level reset would all look like this. The endpoint still reports its IDs and a Gen4 x2 link in sysfs, so its PCIe side is alive.
- This explains the unrecoverable `-19`: the driver re-enables the device but never restores BAR0, so MMIO still reads all-ones. It also explains why `remove` + rescan worked on 2026-08-29: re-enumeration reprograms the BARs. Inference from local state and upstream driver behavior, not yet tested on this event.
- The kernel timestamp is detection time, not failure time. The drive stopped answering between 17:41:34 and about 17:42:36, and the log line came about a minute later when an admin command timed out.
- The namespace was idle but the controller was not untouched: the sampler's temperature read and udisks housekeeping both issue admin commands. A loss noticed on a command after idle fits a low-power-exit problem but does not prove it.
- Temperature was unremarkable: 42.9 °C against a recorded range of 35.9–55.9 °C over 15 531 samples.
- The link never showed degradation: no sample in this log, 17 851 total, was below Gen4 x2. `current_link_*` and `link/*aspm` still read normally after the loss, so they cannot detect this failure and cannot rule out a link event between samples.
- No data was at risk this time: unmounted, no writes.

**What this rules out / weakens:** H4 (thermal) strongly weakened. H5 still rejected. H2/H3/H6 and a power-glitch form of H1 remain; this event does not separate them.

**Instrument defects this event exposed:**
- `discover_mini_ssd` classifies from sysfs presence and never reads the controller `state`, so all 2 320 samples after the loss recorded `NVME_PRESENT` for a `dead` controller with a 0-byte namespace. The null `temperature_c` is the only trace of the loss in the log. Fixed 2026-11-02: only a `live` controller counts as `NVME_PRESENT`.
- The temperature read is not passive (see Instrumentation). It wakes the drive once a minute. The 2026-08-29 and 2026-09-19 losses predate the sampler, so it is not required for the failure, but it cannot be ruled out as a contributor to this one.

**Conclusion:** HYPOTHESIS. Failure layer refined to "endpoint lost its PCI configuration without host action". Cause unresolved.

**Next smallest discriminating experiment:** disable APST alone with `nvme_core.default_ps_max_latency_us=0`, leaving ASPM on and the sampler unchanged. At about one loss every 3–4 weeks, 60 clean days would be needed before crediting it (about a 10% chance of that gap by luck alone). A loss with APST off would rule out APST and move ASPM L1.2 to the next single variable. A clean run still does not qualify the drive.

### OBS-2026-08-29-01 — Two controller losses under active I/O in one boot (passive observation)

Discovered 2026-10-18 by the cross-boot capture (`mini_ssd_events`); missed by the earlier hand review, which only covered boots since 2026-09-07. Not a designed experiment. Operator actions below are reconstructed from the journal's `sudo` records.

**Baseline:**
- boot started 2026-08-29 09:19 MST, BIOS `V1.01`, Mini SSD `nvme0` in this boot
- 09:34 — partition mounted r/w through udisks (desktop automount); writes followed
- no suspend in this boot before the first loss (first `PM: suspend entry` at 11:09)
- Frost Bay: not involved

**Loss 1 — 09:48:22 MST, 14 min after mount, writes in flight:**

```text
nvme nvme0: controller is down; will reset: CSTS=0xffffffff, PCI_STATUS=0x10
nvme 0000:c4:00.0: enabling device (0000 -> 0002)
nvme nvme0: Disabling device after reset failure: -19
EXT4-fs warning (device nvme0n1p1): ext4_end_bio:369: I/O error 10 writing to inode ...
EXT4-fs (nvme0n1p1): failed to convert unwritten extents to written extents -- potential data loss!
EXT4-fs (nvme0n1p1): Delayed block allocation failed ... This should not happen!! Data will be lost
Aborting journal on device nvme0n1p1-8.
EXT4-fs (nvme0n1p1): Remounting filesystem read-only
```

**Operator recovery (11:45–11:51):** PCI rescan; a write to `pcie_aspm` `policy`; two grub edits with `update-grub`; `nvme reset /dev/nvme0`; `lspci -vv`; then `remove` on `0000:c4:00.0` followed by a rescan. The endpoint re-enumerated at 11:51:35 (BAR reassigned, `Max Payload Size set to 256`), `nvme0` probed normally, ext4 ran journal recovery and remounted r/w at 11:51:47.

**Loss 2 — 11:58:09 MST, 6.5 min after re-mount, a read in flight:**

```text
nvme nvme0: controller is down; will reset: CSTS=0xffffffff, PCI_STATUS=0x10
nvme0n1: I/O Cmd(0x2) @ LBA 2504628800, 64 blocks, I/O Error (sct 0x3 / sc 0x71)
nvme 0000:c4:00.0: enabling device (0000 -> 0002)
nvme nvme0: Disabling device after reset failure: -19
```

`sct 0x3 / sc 0x71` is path-related status "Command Aborted By Host", i.e. the host aborted the read because the controller vanished. It is not a media error.

**Aftermath:** the namespace stayed gone for the rest of the boot; every later `s2idle` attempt logged `nvme 0000:c4:00.0: PM: failed to suspend async: error -16` (14 attempts). The next cold boot re-enumerated the drive normally.

**Reading of the evidence:**
- Same signature as OBS-2026-09-19-01 (all-ones CSTS with config space still readable, command register cleared, reset `-19`), so the three losses are one failure mode, not three.
- Both losses here were under active I/O minutes after mounting, so the failure is not confined to long idle. Whatever the trigger is, it can fire within the first 15 minutes of use.
- A software `remove`/rescan brought the device back without touching it physically, and it failed again 6.5 minutes later: a pure contact fault is a poor fit, though not excluded.
- Loss 1 caused real data loss on the ext4 filesystem (`Data will be lost`). This is the concrete reason the `NOT_QUALIFIED` state and the "never the only copy" rule exist.

**What this rules out / weakens:** H5 rejected (filesystem is the victim). H1 weakened. H4 cannot be assessed (no temperature capture existed). H2/H3/H6 remain.

**Conclusion:** HYPOTHESIS unchanged for H2/H3/H6; the trigger window now includes early active use, not only deep idle. The 2026-08-29 grub/ASPM changes are not present on the current kernel command line (see Local evidence notes), so no variable has been changed yet.

**Next smallest discriminating experiment:** unchanged — run the passive capture and mount the drive for ordinary use so the next event carries link/ASPM/temperature context; then change exactly one variable.

### OBS-2026-09-19-01 — Spontaneous controller loss during idle (passive observation)

Discovered 2026-10-18 by journal review; not a designed experiment. Same signature as OBS-2026-08-29-01.

**Baseline:**
- kernel: `7.0.0-30-generic` era boot (boot started 2026-09-18 18:56 MST)
- BIOS: `V1.01`
- power state: on AC/idle desktop session, ~11 h after boot, **no suspend had occurred in that boot** (first `PM: suspend entry` came 10 h later)
- Mini SSD state before event: `NVME_PRESENT` (`nvme0` in that boot), partition unmounted
- Frost Bay: not involved

**Captured evidence (kernel log, 2026-09-19 06:07:13 MST):**

```text
nvme nvme0: controller is down; will reset: CSTS=0xffffffff, PCI_STATUS=0x10
nvme nvme0: Does your device have a faulty power saving mode enabled?
nvme nvme0: Try "nvme_core.default_ps_max_latency_us=0 pcie_aspm=off pcie_port_pm=off" and report a bug
nvme 0000:c4:00.0: enabling device (0000 -> 0002)
nvme nvme0: Disabling device after reset failure: -19
```

**Reading of the evidence:**
- `CSTS=0xffffffff` → controller BAR reads returned all-ones: the device stopped responding on the link.
- `PCI_STATUS=0x10` → config space was still readable, so the endpoint had not fully vanished from the bus at that instant.
- `enabling device (0000 -> 0002)` → the PCI command register had been cleared to 0; the device had lost its configured state (consistent with an internal reset/power cycle or an unhandled low-power exit).
- reset failure `-19` (`ENODEV`) → the kernel gave up and the namespace disappeared for the rest of that boot. The next cold boot re-enumerated it normally.

**Layer classification:** failure sits at the **PCIe link / device power-state** boundary, above physical presence (config space answered) and below the NVMe controller (CSTS unreadable). Maps to `PCIE_ONLY` → effectively `ABSENT` for I/O.

**What this rules out / weakens:**
- H5 (filesystem/application): nothing was mounted; rejected for this event.
- H4 (thermal): idle at 06:07 with no load; weakened for this event (no temperature capture exists for that moment).
- H1 (seating): not excluded, but a contact fault typically shows as enumeration failure at boot rather than an 11-hour-in loss on a stationary device.

**Conclusion:** HYPOTHESIS strengthened for H2 (ASPM/L1.2/clkpm) and H3 (APST / controller firmware power state); H6 (defective unit) remains possible.

**Next smallest discriminating experiment:** none yet — first build passive instrumentation (per-boot event capture keyed by PCI address, periodic link-state/temperature sampling) so the *next* event arrives with context. Only then change one variable (`nvme_core.default_ps_max_latency_us=0` is the smallest and most reversible candidate).

Use the template in `RESEARCH_METHOD.md` for any designed experiment.

## Definition of solved

One of the following is required:

### Software/firmware solution

A specific root cause is supported by evidence and a minimal fix/quirk/firmware update survives the reliability suite.

### Hardware diagnosis

Evidence shows the failure occurs below the layer software can reasonably repair, with enough repeatability to justify replacement/service or avoiding the slot/device.

### Safe mitigation

If the root cause cannot be eliminated, a bounded mitigation is documented with its limits, and Super X Helper can detect/report when the device leaves the safe operating state.

Anything weaker remains an open investigation.