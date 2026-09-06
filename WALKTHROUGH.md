# Super X Helper — Phase 1 & Phase 2 Walkthrough

**Target Device:** ONEXPLAYER Super X (Liquid-Cooled Edition)  
**Date:** 2026-09-06  
**Status:** Completed and Verified

---

## 1. Overview of Accomplishments

This work completed **Phase 1** (The Hardware/Software Property Baseline) and **Phase 2** (Existing Linux Controls & Upstream Ownership):

1. **Hardware & Firmware Inventory Baseline (`SX-001`)**:
   - Recorded the full hardware, APU, display, battery, and storage baseline in [`docs/local-hardware-baseline.md`](docs/local-hardware-baseline.md).
   - Confirmed APU: AMD RYZEN AI MAX+ 395 w/ Radeon 8060S (Strix Halo, 16C/32T) running Linux 7.0 on Ubuntu 24.04.4 LTS.
   - Identified dual NVMe topology: KIOXIA 2TB primary (PCIe Gen4 x4, `c3:00.0`) and BIWIN Mini SSD 2TB removable (PCIe Gen4 x2, `c4:00.0`).
   - Verified that `oxpec.ko.zst` is present in the kernel tree and matches DMI alias `rnONEXPLAYERSUPERX:`.

2. **Upstream Ownership & Linux Integration Matrix (`SX-002`)**:
   - Documented in [`docs/LINUX_INTEGRATION.md`](docs/LINUX_INTEGRATION.md) and [`docs/UPSTREAM_OWNERSHIP.md`](docs/UPSTREAM_OWNERSHIP.md).
   - Defined clear ownership boundaries:
     - Fans: Super X Helper owns via `oxpec` hwmon `pwm1` (with automatic rollback to mode 2 on shutdown).
     - Gamepad / Input: Yield to HHD / InputPlumber / Steam; no redundant controller stack.
     - CPU Scaling: Coordinated profile management via `amd-pstate-epp` and RAPL.
     - Frost Bay: Project-owned exclusive BLE reverse-engineering and control.
     - Mini SSD: Project-owned background health monitoring and fault classifier.

3. **Dynamic Capability Discovery (`src/superx_helper/capabilities.py`)**:
   - Implemented dynamic sysfs interface discovery without hardcoded hwmon numbers (`find_hwmon_by_name`).
   - Added automated detection of contending daemons (`hhd`, `inputplumber`, `power-profiles-daemon`, `tuned`, `tlp`).
   - Added state classification for Mini SSD (`NVME_PRESENT`, `PCIE_ONLY`, `ABSENT`).

4. **Platform Control Backend (`src/superx_helper/platform.py`)**:
   - Built `PlatformBackend` class with strictly validated, typed hardware controls:
     - `set_fan_duty(0..100%)` -> converts to `0..255` on `pwm1`
     - `set_fan_auto()` -> sets `pwm1_enable = 2`
     - `set_epp("performance" | "balance_performance" | ...)` -> checks against available preferences
     - `set_cpu_boost(True | False)`
     - `set_display_brightness_percent(0.0..100.0%)`
   - Adheres to safety invariants: no arbitrary sysfs write strings, verifies observed state against target state, supports dry-run mode.

5. **Diagnostic Collector (`src/superx_helper/collector.py`)**:
   - Zero-dependency CLI tool (`superx-diag` or `python3 -m superx_helper.collector`).
   - Added Section 7 displaying upstream controls and ownership states.
   - Captured timestamped JSON telemetry in [`docs/snapshots/baseline_snapshot.json`](docs/snapshots/baseline_snapshot.json).

---

## 2. Verification Results

### Unit Test Suite
12 unit tests covering collector parsing, dynamic hwmon resolution, capability detection, range checks, and dry-run execution:
```bash
$ PYTHONPATH=src python3 -m unittest discover -s tests -p "test_*.py"
............
----------------------------------------------------------------------
Ran 12 tests in 0.120s

OK
```

### Live Diagnostic Run Output
```text
============================================================
          ONEXPLAYER Super X — Diagnostic Baseline          
============================================================
Timestamp (UTC): 2026-09-06T21:30:12.808699+00:00

--- [1. Device & Firmware Identity] ---
Vendor / Product: ONE-NETBOOK / ONEXPLAYER SUPER X
Board / Version : ONEXPLAYER SUPER X (rev onec1)
BIOS            : V1.01 (01/06/2026) by American Megatrends International, LLC.

--- [2. OS & Platform Kernel] ---
OS              : Ubuntu 24.04.4 LTS (Noble Numbat)
Kernel          : 7.0.0-30-generic
oxpec Driver    : AVAILABLE (Not Loaded) [Module: True]

--- [3. APU & CPU Scaling] ---
CPU Model       : AMD RYZEN AI MAX+ 395 w/ Radeon 8060S
Topology        : 32 logical threads
Scaling Driver  : amd-pstate-epp (Governor: powersave)
EPP Preference  : balance_performance (Boost: Enabled)

--- [4. Storage Topology] ---
[MINI SSD] BIWIN Mini SSD 2TB (nvme0, FW: BS14552T)
   PCI Slot: 0000:c4:00.0 (1dee:2268) | Link: 16.0 GT/s PCIe x2 (Max: 16.0 GT/s PCIe x2)
   State Classification: NVME_PRESENT | Block Devices: 
[INTERNAL SSD] KIOXIA-EXCERIA PLUS G4 SSD (nvme1, FW: EVFAJ1.2)
   PCI Slot: 0000:c3:00.0 (1e0f:0033) | Link: 16.0 GT/s PCIe x4 (Max: 32.0 GT/s PCIe x4)
   State Classification: NVME_PRESENT | Block Devices: 

--- [5. Thermals & Power] ---
  acpitz (hwmon1): temp1: 0.0°C
  BAT0 (hwmon2): power1: 0.0W
  nvme (hwmon3): Composite: 40.9°C, Sensor 1: 40.9°C
  nvme (hwmon4): Composite: 44.9°C, Sensor 1: 44.9°C, Sensor 2: 38.9°C
  mt7925_phy0 (hwmon6): temp1: 57.0°C
  k10temp (hwmon7): Tctl: 63.1°C
  amdgpu (hwmon8): edge: 63.0°C, PPT: 29.1W
Battery Status  : Not charging (99%) | Capacity: 79.84 Wh / 80.9 Wh (Design: 85.58 Wh)

--- [6. Display & Peripherals] ---
Display Output  : card1-HDMI-A-1 [connected] - Mode: 3840x2160
Display Output  : card1-eDP-1 [connected] - Mode: 2880x1800
Backlight       : amdgpu_bl1 at 87.7% (raw: 433882/495000)
Bluetooth       : 1 adapter(s) found
Known USB Device: 1a2c:b001 (ONE NETBOOK)
Known USB Device: 0e8d:0717 (Wireless_Device)
Known USB Device: 2808:5952 (FocalTech Fingerprint Device)

--- [7. Upstream Controls & Ownership] ---
Ownership State : UNCONTESTED
Fan Control     : Available in tree (not loaded)
CPU Power/Boost : Method: rapl | Boost: Available | EPP: Available
Backlight       : Available
Mini SSD State  : NVME_PRESENT (Slot: 0000:c4:00.0)
Daemon Contention: None detected
============================================================
```

---

## 3. Handoff Notes for Next Model / Task

- **Next Phase Recommended in Roadmap:** Frost Bay BLE Discovery & Protocol Reverse Engineering (`Phase 1 / SX-FB-001`).
- **Relevant Docs for Next Agent:**
  - [`docs/FROST_BAY.md`](docs/FROST_BAY.md)
  - [`docs/UPSTREAM_OWNERSHIP.md`](docs/UPSTREAM_OWNERSHIP.md)
  - [`docs/local-hardware-baseline.md`](docs/local-hardware-baseline.md)
- **Host Module Activation:** `sudo modprobe oxpec` should be added to `/etc/modules-load.d/oxpec.conf` by the host administrator to make fan PWM controls active in hwmon on boot.
