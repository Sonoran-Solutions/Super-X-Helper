# Frost Bay — Public Protocol Intake and Local Super X Validation

**Last research refresh:** 2026-09-22

## Objective

Implement safe Linux discovery, telemetry, control, freshness/health handling, and eventual liquid-power gating for the ONEXPLAYER Frost Bay cooler attached to the Super X.

The protocol is **no longer considered undocumented**. Public Linux work now provides a concrete reference implementation and two active HHD integrations. Super X Helper's remaining job is independent local reproduction and safe integration into our capability contract.

## Current status

**External protocol evidence: high confidence.**
**Local Super X/Frost Bay validation: not yet performed.**
**Production capability state: RESEARCH_PENDING / writes blocked.**

Primary sources:

- [tbitu/onexplayer-frostbay-bluetooth](https://github.com/tbitu/onexplayer-frostbay-bluetooth)
- [hhd-dev/hhd PR #321](https://github.com/hhd-dev/hhd/pull/321)
- [hhd-dev/hhd PR #336](https://github.com/hhd-dev/hhd/pull/336)

Do not confuse a public verified implementation with local authorization. Until the development unit reproduces the required identity, transport, telemetry, freshness, and recovery behavior, Super X Helper must keep Frost Bay disabled.

## Publicly established protocol model

The public reference describes Frost Bay as a normal BlueZ/GATT device once the OS has a valid session:

- primary Frost Bay service: FFE0;
- primary state/control characteristic: FFE1;
- direct BlueZ D-Bus ReadValue/WriteValue works after Device1 reports Connected and ServicesResolved and the characteristic is present;
- no proprietary pre-read unlock handshake is required;
- FFE1 reads as a 64-byte state value;
- active mode families include OFF, Smart, and Fixed;
- fan/pump control and water/flow/runtime telemetry are represented within that state;
- writes use a known multi-chunk FFE1 transport rather than a raw 64-byte write.

The exact byte-level reference remains upstream. Super X Helper should link to it and implement only the fields it needs, preserving unknown bytes rather than reinterpreting the entire state.

## Important runtime distinction

The public work distinguishes **requested/stored mode** from **actual runtime activity**. A non-off requested mode must not automatically be treated as proof the cooler is actively healthy.

That maps cleanly to our safety rule:

    requested mode != fresh positive cooler health

A future Liquid Performance profile must require recent validated telemetry and a defined fallback on disconnect/staleness/fault.

## BlueZ transport risk

Public testing on an OneXPlayer Apex found an important Linux-specific failure mode:

- BlueZ could claim the device was connected/services-resolved while the expected Frost Bay GATT subtree was incomplete on the built-in adapter;
- an external adapter exposed the full GATT tree and stable FFE1 access;
- Frost Bay's HID side effects could create bogus volume key events and required targeted host mitigation.

This may or may not reproduce on the Super X. It is now the first local research question.

## Local validation plan

### FB-VAL-001 — Identify the local device

Record:

- advertised/local name;
- address type with public-output redaction;
- firmware/device identity where exposed;
- BlueZ adapter used;
- Connected / ServicesResolved state.

Do not assume the Apex's exact identity or adapter behavior matches the Super X.

### FB-VAL-002 — Reproduce FFE0/FFE1 on the built-in adapter

Using BlueZ D-Bus:

1. connect through normal OS Bluetooth ownership;
2. wait for Connected and ServicesResolved;
3. confirm FFE0 in the device UUIDs;
4. confirm a GattCharacteristic1 object for FFE1;
5. read the state;
6. verify freshness over repeated reads/notifications.

If the GATT subtree is missing, treat this first as a transport/controller problem—not as evidence the protocol is wrong.

### FB-VAL-003 — External-adapter fallback if required

If the built-in adapter is unreliable, reproduce the same sequence with a known-working external adapter and compare:

- service tree;
- characteristic visibility;
- read stability;
- reconnect behavior;
- HID side effects.

Document the result as a supported/unsupported transport matrix.

### FB-VAL-004 — Confirm minimum telemetry semantics

Independently verify only the fields needed for safe UI/health:

- requested mode;
- runtime activity;
- water temperatures;
- flow;
- fan command/state;
- pump command/state;
- timestamp/freshness.

Use external already-supported actions or known-good behavior to correlate values. Do not broaden the task into rediscovering every byte.

### FB-VAL-005 — Read-only backend

Implement BlueZ transport + protocol parsing behind the existing Frost Bay capability records.

Required states include at least:

- unavailable/not discovered;
- connecting;
- connected but services incomplete;
- fresh telemetry;
- stale telemetry;
- fault/invalid frame;
- disconnected.

### FB-VAL-006 — First safe write reproduction

Only after read behavior is locally stable:

- start from a known-good current state;
- reproduce one published benign/reversible command;
- record before state;
- apply the smallest change;
- read back;
- restore;
- verify restoration.

Do not pair first-time Frost Bay writes with increased APU/TDP.

### FB-VAL-007 — Production health contract

Define the exact conditions that satisfy cooler health for liquid-only policy. At minimum, communication freshness and runtime telemetry must matter; stored/requested mode alone is insufficient.

## Work explicitly superseded

The following old tasks are no longer default work:

- discovering FFE0/FFE1 from scratch;
- generic vendor-binary archaeology to find basic Frost Bay commands;
- an Astra mission whose goal is merely to decode the basic protocol;
- blind characteristic probing/fuzzing;
- assuming no public Linux implementation exists.

Escalate to targeted reverse engineering only if local Super X evidence contradicts the public reference in a way the existing implementations do not explain.

## HHD integration notes

PR #321 is a Frost Bay plugin aimed at OneXPlayer Apex and Super-X/Super-V and documents Bluetooth-stack issues separately from the core protocol.

PR #336 implements a broader cooling-dock plugin with BLE synchronization, fan/RGB control, disconnect-aware UI, and tests. HHD review pushed power/TDP concerns toward separation from the dock implementation.

Super X Helper should take the same architectural lesson:

    Frost Bay backend produces validated cooler state
            ↓
    profile/power policy consumes that state

Do not bury dock detection inside a legacy TDP writer.

## Safety invariant

A disconnected, stale, partial-GATT, unknown, or faulted Frost Bay state is **not healthy**.

Published upstream behavior is evidence. Local production authorization still requires reproduction on the development Super X.
