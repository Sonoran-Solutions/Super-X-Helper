# AGENTS.md — Super X Helper

This repository interacts with real cooling, power, Bluetooth and storage hardware. Hardware state and user data are higher priority than task completion speed.

## Current project phase

The current goal is the **pre-Astra daily-driver build**.

Order:

```text
trusted read-only evidence
→ stable capability/service contract
→ GTK daily-driver UI + ordinary Linux integration
→ PRE-ASTRA GATE
→ Frost Bay / Mini SSD deep research
```

Do not jump into Frost Bay protocol writes or Mini SSD fault experiments while doing ordinary frontend/backend work.

## Required reading

Before changing code:

- `README.md`
- `DESIGN.md`
- `ROADMAP.md`
- `docs/UI_CONTRACT.md`
- `docs/PHASE0_HANDOFF.md`
- the relevant hardware research doc.

## Evidence levels

Use evidence in this order:

1. direct observation from the current Super X;
2. upstream kernel/official documentation;
3. reproducible maintained open-source behavior;
4. static vendor-software evidence;
5. community reports;
6. hypothesis.

Never silently upgrade a plausible interface into a locally verified hardware operation.

## Capability states

Frontend/backend state uses:

- `CONFIRMED_LOCAL`
- `SUPPORTED_UNVERIFIED`
- `READ_ONLY`
- `RESEARCH_PENDING`
- `UNAVAILABLE`
- `ERROR`

Mini SSD reliability is `NOT_QUALIFIED` until the qualification track passes.
Frost Bay is `RESEARCH_PENDING` until protocol research passes.

## Discovery is not authorization

This is a hard invariant:

```text
writable path discovered != write authorized
```

The production backend defaults to **no authorized writes**. A write is enabled only after the capability passes the research-to-production gate and policy explicitly authorizes it.

Frontend code checks the normalized contract (`can_write`); it never infers writability from a path or status string.

## UI architecture rules

The frontend may consume only the service/client contract. It must not import raw platform/storage/Frost Bay backends.

Preferred flow:

```text
GTK UI
  ↓ ServiceClient
service facade / D-Bus adapter
  ↓
backend
```

Do not place shell commands, sysfs paths, EC registers or BLE packet bytes in widgets, profiles or user configuration.

## EC/platform safety

- no undocumented EC writes for convenience;
- prefer `oxpec`, hwmon, sysfs, D-Bus or maintained userspace interfaces;
- validate range/type before every write;
- read observed state and fail if it does not match the request;
- failed prerequisites abort dependent operations;
- do not claim automatic fan rollback until it is implemented and tested;
- never disable firmware thermal protections.

## Frost Bay safety

Research order:

1. passive device discovery;
2. GATT map;
3. safe reads/notifications;
4. static OneXConsole analysis;
5. controlled known-good Windows observation if needed;
6. one understood benign Linux write;
7. repeatability/disconnect behavior;
8. typed production backend.

No blind writes, fuzzing, unexplained replay, or max-value first tests.

Loss/staleness/unknown cooler state never means healthy.

## Mini SSD safety

Assume the Mini SSD is untrusted storage until qualification passes.

Failure-layer order:

```text
PCIe endpoint
→ NVMe controller
→ namespace/block device
→ I/O
→ filesystem/application
```

Do not format/repartition/sanitize/firmware-update or run destructive workloads unless an explicit later task and disposable-data setup authorize it.

Do not infer reliability from SMART/enumeration alone.

## Diagnostics/privacy

Default diagnostics:

- are read-only;
- do not start a Bluetooth scan;
- redact unique SSD serials/Bluetooth addresses;
- exclude credentials, usernames, filesystem contents and unrelated personal data where practical.

Explicit local identifier opt-in is allowed when it is genuinely needed for diagnosis.

## Model ladder

- **Tier 1:** Gemini 3.8 Flash / DeepSeek V4 Flash — UI/scaffolding/tests/docs/mechanical work.
- **Tier 2:** GPT-5.6 Terra — serious engineering, Linux/backend integration, review.
- **Tier 3:** DeepSeek V4 Pro — hard debugging/static RE.
- **Tier 4:** GPT-6 Astra — undocumented protocol/fault-isolation research.

Astra should inherit evidence from cheaper models. After research resolves an unknown, step back down for implementation.

## Tests

Default tests/CI must never write physical hardware. Fake sysfs and recorded/mocked protocol data are preferred.

Hardware-changing tests must be explicit, opt-in and document the intended change/rollback.

## Documentation

When a hardware/interface fact changes status, update the relevant doc in the same change. Important discoveries must not exist only in terminal scrollback or an AI conversation.
