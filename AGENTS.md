# AGENTS.md — Super X Helper

This repository contains software that may interact with real hardware, cooling controls, power limits, Bluetooth peripherals, and storage containing user data. Agents must treat hardware state and user data as higher priority than task completion speed.

## Project goal

Build a Linux-native control and diagnostics layer for the ONEXPLAYER Super X, with special focus on:

1. integrating existing Linux platform controls into one safe interface;
2. reverse-engineering and implementing Frost Bay liquid-cooler control/telemetry over Bluetooth;
3. isolating and mitigating Mini SSD reliability failures.

Read `README.md`, `DESIGN.md`, and the relevant research document before changing code or conducting experiments.

## Authority of evidence

Use this priority order:

1. direct observation from the current Super X hardware;
2. upstream Linux/kernel source and official hardware documentation;
3. reproducible behavior from maintained open-source projects;
4. static evidence from publicly distributed vendor software;
5. community reports;
6. inference/hypothesis.

Never silently promote a community report or plausible guess into a confirmed protocol fact.

Use these terms consistently:

- **CONFIRMED** — repeated direct evidence or authoritative source.
- **LIKELY** — strong converging evidence, incomplete direct validation.
- **HYPOTHESIS** — plausible and testable.
- **REJECTED** — contradicted by evidence.

## Hardware safety rules

### EC / platform control

- Do not write undocumented EC registers merely because they appear writable.
- Prefer upstream `oxpec`, hwmon, sysfs, DBus, or maintained userspace interfaces.
- If raw EC access is necessary for research, start read-only and document every register observation.
- Any write experiment requires a specific hypothesis, known prior value, bounded safe candidate value, and rollback plan.
- Never disable platform thermal protection or firmware safety mechanisms as a shortcut.

### Frost Bay

- Start with passive BLE discovery, reads, and notifications.
- Do not fuzz writable GATT characteristics against live cooling hardware.
- Do not replay unexplained byte sequences.
- Before the first Linux control write, document:
  - target device identity;
  - service and characteristic;
  - command meaning;
  - encoding;
  - known safe range;
  - expected effect;
  - rollback/restoration action.
- Do not use maximum pump/fan/power values as first tests.
- Loss of Frost Bay connection/health must never be treated as permission to retain a liquid-only high-power profile.

### Mini SSD

- Assume the Mini SSD is untrusted storage until reliability qualification passes.
- Do not store the only copy of any important file on it.
- Do not format, repartition, erase, sanitize, firmware-update, or run destructive write tests without an explicit task requiring that action and an explicit user-approved disposable-data setup.
- Default diagnostics must be read-only.
- Controlled writes, when authorized, must operate only on clearly identified disposable test files/filesystems.
- Do not blame the filesystem before checking whether the PCIe endpoint and NVMe controller remain present.

## Experimental method

For ambiguous hardware behavior, use:

```text
observation
→ hypothesis
→ prediction
→ smallest discriminating experiment
→ result
→ update hypothesis
```

Change one variable at a time where practical.

For every experiment record:

- timestamp;
- hardware/software baseline relevant to result;
- exact action;
- expected observation;
- actual observation;
- logs/artifacts created;
- conclusion;
- next experiment.

Do not stop at an interesting breadcrumb if another bounded experiment can resolve the immediate question safely.

## Frost Bay reverse-engineering order

Unless evidence requires otherwise:

1. Linux Bluetooth device discovery.
2. GATT service/characteristic enumeration.
3. Read and notification capture.
4. Static OneXConsole inspection for names/UUIDs/constants/protocol structures.
5. Controlled known-good Windows behavior capture if still needed.
6. Reproduce one understood benign command on Linux.
7. Repeatability and disconnect behavior.
8. Typed protocol implementation and tests.

Do not jump directly to step 6.

## Mini SSD investigation order

Always determine the failure layer first:

```text
PCIe endpoint
  ↓
NVMe controller / namespace
  ↓
block device
  ↓
I/O
  ↓
filesystem/application
```

Capture state at the highest available layers after every failure.

Do not apply a bag of kernel parameters simultaneously. Test the minimum evidence-backed change required to discriminate a hypothesis.

## Coding principles

- UI code must not contain raw EC register writes or BLE magic packets.
- Privileged hardware access belongs behind a narrow daemon/API boundary.
- Validate numeric ranges before writes.
- Prefer typed command/state models over raw strings/byte arrays.
- Avoid `shell=true` or command construction from user-controlled strings.
- External helper execution should use fixed executable names/paths and argument arrays.
- Keep research tooling separate from production control paths.
- Hardware-dependent tests must be opt-in and clearly labeled.
- Default CI must not require Super X hardware and must never perform hardware writes.

## Documentation requirements

When a protocol field, sysfs path, EC behavior, or Mini SSD failure mechanism becomes confirmed, update the corresponding `docs/` research file in the same change.

Do not allow key hardware knowledge to exist only in an AI conversation or terminal scrollback.

## Task completion

A research task is not complete merely because a likely cause or candidate byte pattern was found.

Complete when either:

A. the hypothesis has been validated to the task's acceptance criteria and documented; or

B. a specific blocker prevents further safe discrimination with available hardware/artifacts, and the exact next experiment is documented.

Implementation tasks should include tests/fixtures where practical and state any hardware verification still required.