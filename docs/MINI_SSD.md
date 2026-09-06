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

**Status:** HYPOTHESIS.

### H2 — PCIe power-management / ASPM transition

**Why plausible:** intermittent NVMe disappearance often warrants checking link power state, but no local evidence exists yet.

**Prediction:** endpoint/controller loss correlates with a specific idle/suspend transition and can be changed reproducibly by one targeted power-management experiment.

**Status:** HYPOTHESIS.

### H3 — NVMe controller power state / firmware

**Prediction:** PCIe endpoint remains while controller resets/timeouts or namespace disappears; kernel logs show NVMe-level failure.

**Status:** HYPOTHESIS.

### H4 — thermal instability

**Why plausible:** very small high-performance storage has limited thermal mass and community reports mention high temperatures.

**Prediction:** failures correlate strongly with temperature/load, while cold/idle operation remains reliable; PCIe/NVMe errors appear near a repeatable thermal threshold.

**Status:** HYPOTHESIS.

### H5 — filesystem/application issue

**Prediction:** PCIe and NVMe remain fully healthy, raw/block-level checks remain stable, and failures remain specific to filesystem/application behavior.

**Status:** HYPOTHESIS.

### H6 — defective local hardware

**Prediction:** failures persist across OS/kernel/config environments and follow the SSD or slot in a way inconsistent with software controls.

**Status:** HYPOTHESIS.

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

## Experiment log

No local experiments recorded yet.

Use the template in `RESEARCH_METHOD.md` and link each experiment here once work begins.

## Definition of solved

One of the following is required:

### Software/firmware solution

A specific root cause is supported by evidence and a minimal fix/quirk/firmware update survives the reliability suite.

### Hardware diagnosis

Evidence shows the failure occurs below the layer software can reasonably repair, with enough repeatability to justify replacement/service or avoiding the slot/device.

### Safe mitigation

If the root cause cannot be eliminated, a bounded mitigation is documented with its limits, and Super X Helper can detect/report when the device leaves the safe operating state.

Anything weaker remains an open investigation.