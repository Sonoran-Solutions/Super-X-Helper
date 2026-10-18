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

**Status:** HYPOTHESIS — local evidence (OBS-2026-08-29-01, OBS-2026-09-19-01) is consistent with H2/H3, but two of three losses happened under active I/O minutes after mounting, so a pure idle/deep-state trigger is not sufficient. Not yet discriminated from H3 or H6.

### H3 — NVMe controller power state / firmware

**Prediction:** PCIe endpoint remains while controller resets/timeouts or namespace disappears; kernel logs show NVMe-level failure.

**Status:** HYPOTHESIS — local evidence (OBS-2026-08-29-01, OBS-2026-09-19-01) is consistent with H2/H3: every loss is the same signature (`CSTS=0xffffffff`, command register cleared, reset fails with `-19`). Not yet discriminated from H2 or H6.

### H4 — thermal instability

**Why plausible:** very small high-performance storage has limited thermal mass and community reports mention high temperatures.

**Prediction:** failures correlate strongly with temperature/load, while cold/idle operation remains reliable; PCIe/NVMe errors appear near a repeatable thermal threshold.

**Status:** HYPOTHESIS — weakened by the idle loss (OBS-2026-09-19-01) but revived slightly by two losses under active I/O (OBS-2026-08-29-01). No temperature was captured at any event; the new telemetry closes that gap.

### H5 — filesystem/application issue

**Prediction:** PCIe and NVMe remain fully healthy, raw/block-level checks remain stable, and failures remain specific to filesystem/application behavior.

**Status:** REJECTED for the recorded events — ext4 was the victim, not the cause (I/O errors appear only after the controller read all-ones), and one loss happened with nothing mounted.

### H6 — defective local hardware

**Prediction:** failures persist across OS/kernel/config environments and follow the SSD or slot in a way inconsistent with software controls.

**Status:** HYPOTHESIS — three identical losses on one unit are also what a marginal device would look like.

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
- **Kernel command line** carries no `nvme_core`/`pcie_aspm` parameters as of 2026-10-18, so the grub edits attempted during the 2026-08-29 recovery are not in effect and the baseline above is the stock configuration.
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
- `temperature_c` from the `nvme` hwmon whose `device` link resolves under the Mini SSD PCI device (unprivileged; SMART stays unavailable without root).
- sysfs-only, so refreshes stay cheap. The UI snapshot is not persisted, so the sampler below exists to keep a history.

**Periodic sampler** (`superx-mini-ssd-sample`, key `mini_ssd_telemetry_log` in `superx-diag`):

- One run = one JSON line appended to `$XDG_STATE_HOME/superx-helper/mini-ssd-telemetry.jsonl` (default `~/.local/state/superx-helper/`): `timestamp_utc`, `state` (`ABSENT`/`PCIE_ONLY`/`NVME_PRESENT`), `pci_address`, `controller`, `link_speed`, `link_width`, `max_link_*`, `aspm`, `temperature_c`, plus `power` (`l1_1_pcipm`, `l1_2_pcipm`, `clkpm`, `d3cold_allowed`, `runtime_status`: the remaining H2 variables) and `io` (`reads_completed`, `sectors_read`, `writes_completed`, `sectors_written` from `/sys/block/<ns>/stat`, and `mounted`). The I/O counters are cumulative since boot, so activity is the difference between consecutive samples; that is what separates the idle loss from the two under-I/O losses. `mounted` comes from `/proc/self/mountinfo` matched on `/dev/<ns>`; no mount point or other mount detail is stored. Same kind of sysfs reads as above; no journalctl, nvme-cli, mount or drive access, and the log is the only file written. It keeps logging when the drive is absent, so the transition itself is recorded.
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