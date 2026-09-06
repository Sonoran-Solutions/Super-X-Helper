# AGENTS.md — Super X Helper

This repository contains software that may interact with real hardware, cooling controls, power limits, Bluetooth peripherals, and storage containing user data. Agents must treat hardware state and user data as higher priority than task completion speed.

## Project goal

Build a Linux-native control and diagnostics layer for the ONEXPLAYER Super X, with special focus on:

1. integrating existing Linux platform controls into one safe daily-driver application;
2. reverse-engineering and implementing Frost Bay liquid-cooler control/telemetry over Bluetooth;
3. isolating and mitigating Mini SSD reliability failures.

**Current milestone:** finish the pre-Astra daily-driver control center before spending premium research-model effort on Frost Bay or Mini SSD root-cause work. Read `docs/PRE_ASTRA_CHECKPOINT.md` and `ROADMAP.md` before choosing the next task.

The pre-Astra product should already provide ordinary performance/fan/display/battery/profile/diagnostic functionality where Linux exposes a trustworthy interface. Frost Bay should remain `RESEARCH_PENDING`, and Mini SSD reliability should remain `NOT_QUALIFIED`, until their dedicated research gates pass.

Read `README.md`, `DESIGN.md`, and the relevant research document before changing code or conducting experiments.

## Model ladder

Use the cheapest model tier that can reliably do the work:

- **Tier 1 — Gemini 3.8 Flash / DeepSeek V4 Flash:** inventory, scaffolding, UI/components, tests, docs, mechanical implementation.
- **Tier 2 — GPT-5.6 Terra Medium:** serious engineering, backend/system integration, correctness review, hardening of Tier-1 output.
- **Tier 3 — DeepSeek V4 Pro High:** hard debugging, difficult architecture, static reverse engineering, second opinion after serious Tier-2 attempts.
- **Tier 4 — GPT-6 Astra Medium/High:** undocumented protocols, experimental hardware debugging, cross-layer root-cause work, autonomous hypothesis → experiment loops.

**Routing rule:** Astra should usually receive evidence produced by cheaper models rather than being asked to gather all evidence itself. Once Astra resolves an unknown, step back down to Terra/Flash for normal implementation, tests, UI wiring and documentation.

For this project, Astra is primarily reserved for:

- unresolved Frost Bay protocol semantics and the first safe proof-of-control;
- Mini SSD disappearance/root-cause isolation and the first evidence-backed mitigation experiment.

Do not use Astra merely because a task is large or visually important.

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

For UI/backend capability state, do not overload the research confidence labels. Use explicit capability states such as:

- `AVAILABLE_READ_WRITE`
- `READ_ONLY`
- `SUPPORTED_UNVERIFIED`
- `RESEARCH_PENDING`
- `UNAVAILABLE`
- `ERROR`

Capability discovery is not authorization to write hardware.

## Hardware safety rules

### EC / platform control

- Do not write undocumented EC registers merely because they appear writable.
- Prefer upstream `oxpec`, hwmon, sysfs, DBus, compositor APIs, or maintained userspace interfaces.
- A sysfs path existing is not sufficient proof that the exact local write semantics are production-qualified.
- If raw EC access is necessary for research, start read-only and document every register observation.
- Any write experiment requires a specific hypothesis, known prior value, bounded safe candidate value, and rollback plan.
- A failed prerequisite operation must abort dependent writes. Example: failure to enter fan manual mode means do not attempt a subsequent PWM-duty write.
- Where observed state exists, compare it against the requested state rather than treating a successful file write as hardware verification.
- Never disable platform thermal protection or firmware safety mechanisms as a shortcut.

### Frost Bay

- Before the research phase, production code/UI must report `RESEARCH_PENDING` rather than simulate control/telemetry.
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
- The daily-driver UI may show read-only presence/link/temperature/SMART telemetry, but must label reliability `NOT_QUALIFIED` until the research suite passes.
- Do not store the only copy of any important file on it.
- Do not format, repartition, erase, sanitize, firmware-update, or run destructive write tests without an explicit task requiring that action and an explicit user-approved disposable-data setup.
- Default diagnostics must be read-only.
- Controlled writes, when authorized, must operate only on clearly identified disposable test files/filesystems.
- Do not blame the filesystem before checking whether the PCIe endpoint and NVMe controller remain present.
- Do not equate `NVME_PRESENT` or clean SMART telemetry with reliability qualification.

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

## Pre-Astra implementation order

Unless a blocking dependency proves otherwise:

1. harden baseline/capability/collector evidence;
2. establish the privileged service/API boundary;
3. validate ordinary platform write paths one by one;
4. build capability-driven UI shell/dashboard;
5. add Performance, Cooling, Display, Power/Battery, Storage, Profiles and Diagnostics pages;
6. add quick-access workflow;
7. integrate maintained controller/RGB support where practical;
8. pass the pre-Astra checkpoint;
9. only then begin Frost Bay and Mini SSD deep research.

Do not allow a research-pending Frost Bay card or unqualified Mini SSD to block the rest of the product.

## Frost Bay reverse-engineering order

After the pre-Astra checkpoint:

1. Gemini/cheap-model Linux Bluetooth device discovery.
2. GATT service/characteristic enumeration and safe read/notification capture.
3. Terra review/curation of evidence.
4. DeepSeek V4 Pro static OneXConsole inspection for names/UUIDs/constants/protocol structures.
5. Astra receives the curated evidence packet and resolves remaining semantics through minimum safe experiments.
6. Reproduce one understood benign command on Linux.
7. Repeatability and disconnect behavior.
8. Typed protocol implementation and tests with Terra/Flash.

Do not jump directly to the write step.

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
- Privileged hardware access belongs behind a narrow service/API boundary.
- Validate numeric ranges before writes.
- Prefer typed command/state models over raw strings/byte arrays.
- Avoid `shell=true` or command construction from user-controlled strings.
- External helper execution should use fixed executable names/paths and argument arrays.
- Keep research tooling separate from production control paths.
- Hardware-dependent tests must be opt-in and clearly labeled.
- Default CI must not require Super X hardware and must never perform hardware writes.
- UI components must tolerate `READ_ONLY`, `SUPPORTED_UNVERIFIED`, `RESEARCH_PENDING`, `UNAVAILABLE`, and `ERROR` states without hacks.
- Profiles are high-level declarative policy, never raw paths/registers/commands.

## Documentation requirements

When a protocol field, sysfs path, EC behavior, or Mini SSD failure mechanism becomes confirmed, update the corresponding `docs/` research file in the same change.

When a capability becomes production-qualified, update its status/evidence in the relevant Linux integration or architecture documentation.

Do not allow key hardware knowledge to exist only in an AI conversation or terminal scrollback.

## Task completion

A research task is not complete merely because a likely cause or candidate byte pattern was found.

Complete when either:

A. the hypothesis has been validated to the task's acceptance criteria and documented; or

B. a specific blocker prevents further safe discrimination with available hardware/artifacts, and the exact next experiment is documented.

Implementation tasks should include tests/fixtures where practical and state any hardware verification still required.

For pre-Astra work, task completion must not silently upgrade `SUPPORTED_UNVERIFIED` to `AVAILABLE_READ_WRITE` merely because mocked tests pass.