# ONEXPLAYER Super X — Local Hardware & Software Baseline

Captured: 2026-09-06  
Device target: ONEXPLAYER Super X (Liquid-Cooled Edition)

This file records the original direct observations. It does **not** imply that every writable interface mentioned by upstream Linux has been exercised on this device.

## System / firmware

| Property | Captured value |
|---|---|
| System vendor | `ONE-NETBOOK` |
| Product | `ONEXPLAYER SUPER X` |
| Board | `ONEXPLAYER SUPER X` |
| Board revision | `onec1` |
| BIOS vendor | American Megatrends International, LLC. |
| BIOS version | `V1.01` |
| BIOS date | `01/06/2026` |

## OS / kernel

- Ubuntu 24.04.4 LTS (`noble`)
- kernel `7.0.0-30-generic`
- x86_64

## APU

- AMD RYZEN AI MAX+ 395 w/ Radeon 8060S
- 16 cores / 32 threads
- `amd-pstate-epp`
- scaling governor observed: `powersave`
- EPP observed: `balance_performance`
- CPU boost file observed as enabled
- powercap/RAPL interface present

## GPU

- AMD Radeon 8060S
- PCI ID observed: `1002:1586`
- `amdgpu`
- temperature/power telemetry observed through hwmon

## Storage

### Internal SSD

- KIOXIA-EXCERIA PLUS G4 SSD, 2 TB
- `/dev/nvme1n1` observed during the baseline
- firmware `EVFAJ1.2`
- PCIe address `0000:c3:00.0`
- link observed at Gen4 x4

### Mini SSD

- BIWIN Mini SSD 2 TB
- `/dev/nvme0n1` observed during the baseline
- firmware `BS14552T`
- PCIe address `0000:c4:00.0`
- PCI ID `1dee:2268`
- link observed at Gen4 x2

**Reliability state: `NOT_QUALIFIED`.** Current enumeration is not proof that the recurring disappearance problem is solved.

Unique SSD serial numbers are intentionally omitted from this public baseline.

## Display

- internal panel on `card1-eDP-1`
- native mode observed: 2880×1800
- 120 Hz support recorded by the original inventory
- backlight interface `amdgpu_bl1`

## Battery

- `BAT0` telemetry observed
- design energy ~85.58 Wh
- full energy ~80.90 Wh at capture

No trustworthy charge-limit/bypass write path was established by this capture.

## Connectivity / peripherals

- MediaTek MT7925 Wi-Fi/Bluetooth device (`0e8d:0717`)
- Bluetooth stack on `hci0`
- ONE NETBOOK/Semico USB platform device `1a2c:b001`
- FocalTech fingerprint device `2808:5952`

Bluetooth addresses are intentionally omitted.

## `oxpec`

The kernel module file was present and the Super X DMI identity matched upstream support.

**Important:** `oxpec` was **not loaded during the captured baseline**, so the exact live fan hwmon attributes and real fan write behavior were not locally verified at capture time.

Treat fan control as `SUPPORTED_UNVERIFIED` until a deliberate live validation pass confirms:

- exact attributes;
- read behavior;
- manual/automatic transition semantics;
- safe write behavior;
- recovery/rollback behavior.

---

## 2026-09-07 re-capture delta

A fresh read-only capture on the live machine (see `docs/LIVE_INTEGRATION_HANDOFF.md`) confirmed the baseline above and added these observations:

- **External display connected:** `card1-HDMI-A-1` at 3840×2160 in addition to the internal `card1-eDP-1` (2880×1800).
- **Internal SSD PCI ID:** KIOXIA internal NVMe observed as `1e0f:0033` (the original baseline recorded model/firmware/link but not the PCI ID).
- **Backlight requested vs actual:** `amdgpu_bl1` shows requested `brightness` 460697 (≈93.1 %) but `actual_brightness` 433882 (≈87.7 %); noted for future brightness-write validation.
- **`oxpec` correction:** the installed `7.0.0-30-generic` module has **no `ONEXPLAYER SUPER X` DMI quirk** (only `G1 A`/`G1 i` and a legacy `ONE XPLAYER` alias). Upstream added Super X → `oxp_g1_a` after this kernel (commit `0b6573e`). The module would therefore not bind on this host; fan control remains `SUPPORTED_UNVERIFIED`. The driver also registers its hwmon as `oxp_ec`, not `oxpec` (corrected in `capabilities.py`).
