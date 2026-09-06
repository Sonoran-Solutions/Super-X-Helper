# Research Method

Super X Helper uses an evidence-first workflow for hardware and protocol research.

## Why this exists

The project crosses several layers where a plausible-looking software fix can hide the real problem:

- firmware/EC;
- Linux platform drivers;
- Bluetooth/GATT;
- PCIe/NVMe;
- power management;
- thermals;
- userspace controls.

The goal is to avoid turning anecdotes or lucky boots into permanent implementation decisions.

## Standard experiment template

```markdown
## EXP-YYYY-MM-DD-NN — Short title

**Question:**

**Baseline:**
- kernel:
- BIOS:
- power state:
- Frost Bay state:
- Mini SSD state:
- other relevant config:

**Current hypothesis:**

**Prediction if hypothesis is true:**

**Single variable changed:**

**Procedure:**
1.
2.
3.

**Captured evidence:**
- command/log/file:

**Observed result:**

**Conclusion:** CONFIRMED / LIKELY / HYPOTHESIS / REJECTED

**What this rules out:**

**Next smallest discriminating experiment:**
```

## Baseline capture

Before a research session, record at least the relevant subset of:

```bash
uname -a
cat /etc/os-release
cat /sys/class/dmi/id/sys_vendor
cat /sys/class/dmi/id/product_name
cat /sys/class/dmi/id/board_name
lsmod
lspci -nn
lspci -vv
lsusb
bluetoothctl show
nvme list
```

Do not paste Bluetooth pairing secrets or unrelated personal device data into public issues.

## Evidence storage

Small human-readable findings belong in the relevant `docs/*.md` file.

Large logs/captures should not be committed automatically. Record:

- filename;
- checksum if useful;
- collection procedure;
- important excerpts;
- whether the artifact contains sensitive information.

## Change one variable

Avoid experiments such as:

```text
disable ASPM
change NVMe power latency
change kernel
reseat SSD
change filesystem
```

all at once.

A successful boot afterward proves almost nothing.

Prefer:

```text
baseline reproduction
→ change only ASPM behavior
→ repeat exact test
→ compare
```

## Negative evidence matters

Record things that *did not* cause failure.

Examples:

- 10 warm reboots passed;
- failure occurred without suspend;
- PCIe endpoint remained visible during I/O error;
- Frost Bay continued sending notifications with pump setting unchanged.

This prevents later sessions from retesting the same dead ends.

## Research checkpoints

At the end of every substantial session, update:

1. confirmed facts;
2. current hypotheses;
3. rejected hypotheses;
4. exact next experiment;
5. any implementation consequences.

The next engineer/agent should be able to continue from the documents without needing the previous conversation.