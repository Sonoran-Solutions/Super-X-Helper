# Phase-0 Tier-2 Handoff

**Status:** historical Phase-0 handoff. Code hardening completed here; the later 2026-09-07 live integration pass supersedes its hardware assumptions and frontend-next-task guidance.

> **2026-09-22 planning note:** the GTK shell/read-only pages are already implemented; the captured kernel was later proven to lack the Super X `oxpec` DMI quirk; Loadout must be audited before production fan/TDP machinery; and Frost Bay basic protocol discovery has been superseded by public FFE0/FFE1 work. Use `ROADMAP.md`, `docs/LIVE_INTEGRATION_HANDOFF.md`, and `docs/UPSTREAM_OWNERSHIP.md` for current next steps.

## What changed

The Gemini Flash foundation was retained but tightened around evidence and fail-closed behavior.

- Mini SSD presence is now classified from the known PCIe endpoint through NVMe controller **and namespace** presence.
- NVMe namespaces are resolved from the controller and `/sys/class/block`; the previous empty-namespace bug is removed.
- The collector gathers read-only SMART/error fields when `nvme-cli` is available and filtered kernel messages when journal access is available.
- Default public diagnostics redact SSD serials and Bluetooth addresses; identifiers require explicit opt-in.
- Bluetooth inventory remains passive: cached target-like BlueZ devices/services only; no scan is started by the collector.
- Capability discovery and write authorization are separate.
- All platform writes are disabled by default until explicitly production-authorized.
- Sysfs writes now fail if the observed value does not match the requested value.
- A failed manual-fan-mode transition prevents a subsequent PWM duty write.
- No automatic fan rollback is claimed or implemented yet.
- Frost Bay is represented as `RESEARCH_PENDING`.
- Mini SSD reliability is represented as `NOT_QUALIFIED` regardless of current enumeration/SMART state.

## Confirmed local facts from the existing baseline

These facts were directly captured on the development Super X before this pass:

- ONE-NETBOOK / ONEXPLAYER SUPER X, board revision `onec1`;
- BIOS `V1.01`;
- Ubuntu 24.04.4 LTS / kernel 7.0.0-30-generic at capture time;
- AMD RYZEN AI MAX+ 395 / Radeon 8060S;
- `amd-pstate-epp` active, boost exposed, EPP readable;
- internal display present at 2880×1800 with 120 Hz support reported in the baseline;
- `amdgpu_bl1` backlight telemetry present;
- battery telemetry present;
- KIOXIA internal NVMe and BIWIN Mini SSD PCIe/NVMe identities observed;
- Mini SSD observed at PCIe Gen4 x2 during the baseline;
- MediaTek Bluetooth adapter on `hci0` observed;
- `oxpec` module file was present. **Later live integration disproved the original assumption that this kernel contained a Super X DMI match**: Ubuntu kernel `7.0.0-30-generic` lacks the Super X quirk and exposes no live `oxp_ec` hwmon. See `docs/LIVE_INTEGRATION_HANDOFF.md`.

## Production-qualified write capabilities

**None yet.**

This is intentional. The current code can model/write fake sysfs fixtures in tests, but no real hardware write is authorized by default until its exact Super X path passes the production gate.

## Read-only capabilities ready for UI use

- battery telemetry;
- connected display/mode telemetry;
- CPU boost/EPP observed state where exposed;
- brightness observed state;
- thermal/hwmon telemetry;
- Mini SSD PCIe/NVMe presence classification;
- NVMe namespaces;
- Mini SSD link/model/firmware telemetry;
- SMART/error summary when `nvme-cli` permits it;
- filtered relevant kernel messages;
- diagnostics export;
- passive cached Frost-Bay-like Bluetooth device/service inventory if BlueZ already knows the device.

Controls whose read paths exist but writes have not been validated appear as `SUPPORTED_UNVERIFIED`, not production controls.

## Still-unverified ordinary features

- exact live `oxpec` hwmon attributes after loading the module;
- real internal-fan write behavior and safe rollback/recovery;
- CPU boost/EPP write behavior on this exact host;
- direct brightness write behavior under the active compositor/session;
- selected package/APU power-target control mechanism and safe range;
- resolution/refresh/VRR mutation path through the compositor;
- charge limit/bypass charging;
- RGB;
- stable HHD/InputPlumber integration surface for controller/vibration/gyro;
- quick-access trigger from a Super X hardware button.

These are ordinary integration/validation tasks unless evidence turns one into a separate reverse-engineering problem.

## Chosen architecture

See `docs/adr/0001-python-gtk-dbus-architecture.md`.

Summary:

```text
GTK4/libadwaita UI (unprivileged)
            ↓ ServiceClient
system D-Bus / polkit adapter
            ↓
Python superx-helperd service facade
            ↓
platform / storage / future Frost Bay backends
```

Keep the Python core. Use GTK4/libadwaita via PyGObject. Target Ubuntu `.deb` packaging. Keep profiles as versioned high-level JSON under the user's XDG config directory.

## Frontend interfaces implemented after this handoff

The GTK frontend was subsequently built against the intended narrow surface. Frontend code consumes only:

```text
CapabilitySnapshot
CapabilityRecord
CapabilityId
CapabilityStatus
SafetyState
ServiceClient.get_snapshot()
ui_manifest.PAGES
```

It should not import raw hardware backends.

## Test result

Local reconstructed repository test run:

```text
22 tests
OK
```

Coverage added for:

- `ABSENT` / `PCIE_ONLY` / `NVME_PRESENT` Mini SSD states;
- namespace resolution;
- serial redaction + explicit identifier opt-in;
- discovery-not-authority behavior;
- requested-vs-observed mismatch;
- failed manual-fan-mode prerequisite;
- unverified control disabled state;
- Frost Bay `RESEARCH_PENDING` state;
- Mini SSD `NOT_QUALIFIED` state;
- stable UI page manifest.

## Recommended next task — superseded

The frontend task originally recommended here is complete.

Current sequencing is maintained in `ROADMAP.md`. In short:

1. audit Loadout's fan/TDP implementation before building generic production control logic;
2. validate a kernel/backport containing the Super X `oxpec` quirk and inventory `oxp_ec` under root;
3. validate EPP → boost → brightness → fan as separate reversible operations;
4. treat Frost Bay as a local BlueZ/health validation task using the published protocol rather than a from-scratch reverse-engineering mission.
