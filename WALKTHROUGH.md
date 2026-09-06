# Super X Helper — Foundation Walkthrough

**Target:** ONEXPLAYER Super X (Liquid-Cooled Edition)  
**Original capture date:** 2026-09-06  
**Current status:** Gemini foundation reviewed and hardened by a Tier-2 engineering pass.

## What the original Gemini pass accomplished

Gemini 3.8 Flash produced useful first-pass evidence and scaffolding:

- local hardware/software baseline;
- Linux/upstream ownership inventory;
- Python capability discovery;
- read-only diagnostic collector;
- provisional platform backend;
- initial unit tests.

That work was valuable but some original wording overstated what was verified on live hardware.

## Tier-2 corrections

The current repository now distinguishes:

- direct local observations;
- interface support that exists but has not been exercised;
- read-only production state;
- research-pending features;
- unavailable/error states.

Important corrections:

1. `oxpec` was present in the captured kernel but **not loaded during the baseline**. Fan hwmon attributes and real writes therefore remain `SUPPORTED_UNVERIFIED` until explicitly validated.
2. No automatic fan rollback/recovery behavior is currently claimed. It must be implemented and hardware-tested before custom fan curves are production-qualified.
3. CPU boost, EPP and brightness read paths are observed, but their direct write paths are not automatically authorized merely because sysfs files exist.
4. Mini SSD `NVME_PRESENT` now requires namespace/block-device evidence, not merely an NVMe controller object.
5. Mini SSD reliability remains `NOT_QUALIFIED` regardless of current SMART/enumeration state.
6. Frost Bay remains `RESEARCH_PENDING`; no local protocol work was performed in this pass.
7. Default public diagnostics redact unique SSD/Bluetooth identifiers.

## Current test result

The hardened code was reconstructed locally and run through:

```text
22 tests
OK
```

The suite covers presence classification, namespace discovery, redaction, fail-closed write authorization, observed-value mismatch, fan prerequisite failure, capability normalization, Frost Bay research state, Mini SSD qualification state and the UI manifest.

## Current handoff

The next task is **not Frost Bay research**. Build the pre-Astra GTK application shell against the stable frontend contract.

Read:

- `docs/PHASE0_HANDOFF.md`
- `docs/UI_CONTRACT.md`
- `docs/adr/0001-python-gtk-dbus-architecture.md`
- `ROADMAP.md`
