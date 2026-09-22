# Linux Integration Baseline

## Objective

Use existing Linux interfaces wherever they are trustworthy and keep uncertainty explicit. The application is a unifying control center, not a replacement kernel/input stack.

## Captured host

The existing baseline was captured on an ONEXPLAYER Super X running Ubuntu 24.04.4 LTS / kernel 7.0.0-30-generic with board revision `onec1` and BIOS `V1.01`.

## Capability matrix

| Capability | Interface/project | Evidence level | Current application behavior |
|---|---|---|---|
| CPU boost state | `/sys/devices/system/cpu/cpufreq/boost` | locally observed read path | `SUPPORTED_UNVERIFIED`; writes disabled until validated |
| EPP state | `amd-pstate-epp` | locally observed read path | `SUPPORTED_UNVERIFIED`; writes disabled until validated |
| Package power telemetry / target | powercap/RAPL locally; Loadout TDP and HHD are upstream references | telemetry observed; write mechanism not selected | read/inventory only; audit upstream before selecting a production write adapter |
| Internal fan | `oxpec` / `oxp_ec` hwmon; Loadout fan-control as userspace reference | module installed but **no Super X DMI quirk** in this kernel; live module not loaded and would not bind | `SUPPORTED_UNVERIFIED`; audit upstream safety/ownership logic before implementing curves |
| Battery telemetry | power_supply; Loadout battery plugin is an upstream control reference | locally observed telemetry; control not locally proven | `READ_ONLY` |
| Charge limit/bypass | unresolved | not exposed by the captured standard battery interface | `UNAVAILABLE` |
| Thermals | hwmon (`k10temp`, `amdgpu`, `nvme`) | locally observed | `READ_ONLY` |
| Display mode | DRM | locally observed | `READ_ONLY` until compositor mutation path is selected |
| Brightness | amdgpu backlight | locally observed read path | write disabled until live validation |
| Controller/gyro | kernel/HHD/InputPlumber/Steam | device/input stack exists; integration API not selected | external integration follow-up |
| RGB | Loadout/OpenRGB/HHD are upstream references | no local control path selected | unavailable/follow-up; audit maintained implementations first |
| Bluetooth adapter | MediaTek/BlueZ | locally observed `hci0` | safe passive inventory available |
| Frost Bay | BlueZ + published FFE0/FFE1 protocol + HHD implementations | strong public protocol evidence; no local Super X/Frost Bay validation yet | `RESEARCH_PENDING` locally; validate transport/health rather than rediscover protocol |
| Mini SSD presence | PCIe/NVMe | locally observed baseline | read-only presence/link/namespace diagnostics |
| Mini SSD reliability | research task | unresolved recurring failure | `NOT_QUALIFIED` |

## Dynamic discovery rules

- Never hard-code `hwmonN`, `nvmeN`, or a transient device number when stable identity/capability discovery is available.
- Known Mini SSD PCI identity is used to locate the removable device, then the code follows the chain through NVMe controller and namespace.
- `NVME_PRESENT` means a usable namespace/block device exists. A bare PCIe endpoint or controller without a namespace is `PCIE_ONLY` for current presence classification.

## Capability versus authorization

The code intentionally keeps two concepts separate:

```text
interface exists
    ≠
write is production-authorized
```

The UI consumes `CapabilityRecord.can_write`. No control becomes interactive merely because a sysfs file is writable.

## Passive diagnostics

The hardened collector can obtain:

- sysfs/hwmon/DRM/battery state;
- PCIe/NVMe identities and namespaces;
- allow-listed SMART/error fields via `nvme-cli` when available;
- filtered kernel messages via `journalctl` when accessible;
- cached Frost-Bay-like BlueZ device/service metadata without starting a scan.

Unique SSD serials and Bluetooth addresses are redacted by default.

## Next live validation tasks

Before enabling ordinary writes in the UI:

- [x] run the hardened collector and commit/review a fresh redacted snapshot (2026-09-07; see `docs/LIVE_INTEGRATION_HANDOFF.md`);
- [ ] complete the Loadout fan/TDP upstream audit in `SX-UPSTREAM-001` before writing a second generic control stack;
- [ ] update/backport `oxpec` to a kernel containing the Super X quirk, then load it under root and inventory the `oxp_ec` hwmon attributes;
- [ ] validate safe fan read/manual/auto behavior plus tested recovery to firmware/EC ownership, using upstream failure-handling patterns where appropriate;
- [ ] validate CPU EPP and boost writes on the actual host (requires root);
- [ ] validate brightness mutation under the active desktop session (requires root; note the requested-vs-actual gap on `amdgpu_bl1`);
- [ ] select a compositor-aware resolution/refresh/VRR control path;
- [ ] choose an evidence-backed power-target mechanism/range after the Loadout/HHD audit;
- [ ] investigate charge limit/bypass and RGB only after checking maintained upstream implementations.

### `oxpec` on this kernel

The in-tree driver registers its hwmon chip as **`oxp_ec`** (not `oxpec`), so discovery must look for `oxp_ec` with a legacy `oxpec` fallback — corrected in `capabilities.py`.

The installed `7.0.0-30-generic` module has no `ONEXPLAYER SUPER X` DMI quirk. Upstream added Super X → `oxp_g1_a` support after this kernel (commit `0b6573e`). Until that quirk is present, `oxpec` will not bind on the Super X and fan control remains `SUPPORTED_UNVERIFIED`.

Frost Bay remains locally `RESEARCH_PENDING`, but its basic BLE protocol is no longer an unknown: public work documents the FFE0/FFE1 path and HHD has active implementations. After the daily-driver checkpoint, start with local BlueZ reproduction and transport/health validation, not protocol archaeology. Mini SSD fault reproduction remains a separate unresolved research track.
