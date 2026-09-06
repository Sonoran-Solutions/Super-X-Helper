# ONEXPLAYER Super X — Local Hardware & Software Baseline

Captured: 2026-09-06  
Device Target: ONEXPLAYER Super X (Liquid-Cooled Edition)

---

## 1. System & Firmware Identity

| Property | Value | Sysfs / Source |
|---|---|---|
| **System Vendor** | `ONE-NETBOOK` | `/sys/class/dmi/id/sys_vendor` |
| **Product Name** | `ONEXPLAYER SUPER X` | `/sys/class/dmi/id/product_name` |
| **Board Name** | `ONEXPLAYER SUPER X` | `/sys/class/dmi/id/board_name` |
| **Board Version** | `onec1` | `/sys/class/dmi/id/board_version` |
| **BIOS Vendor** | `American Megatrends International, LLC.` | `/sys/class/dmi/id/bios_vendor` |
| **BIOS Version** | `V1.01` | `/sys/class/dmi/id/bios_version` |
| **BIOS Release Date** | `01/06/2026` | `/sys/class/dmi/id/bios_date` |
| **Chassis Type** | `10` (Notebook) | `/sys/class/dmi/id/chassis_type` |
| **DMI Modalias** | `dmi:bvnAmericanMegatrendsInternational,LLC.:bvrV1.01:bd01/06/2026:br5.36:efr0.21:svnONE-NETBOOK:pnONEXPLAYERSUPERX:pvrDefaultstring:rvnONE-NETBOOK:rnONEXPLAYERSUPERX:rvronec1:cvnONE-NETBOOK:ct10:cvrDefaultstring:sku:pfaONEXPLAYERSUPERX:` | `/sys/class/dmi/id/modalias` |

---

## 2. Operating System & Kernel Environment

- **Distribution:** Ubuntu 24.04.4 LTS (`noble`)
- **Kernel Version:** `7.0.0-30-generic` (`#30~24.04.1-Ubuntu SMP PREEMPT_DYNAMIC Fri Aug 7 13:27:52 UTC 2026 x86_64`)
- **Init System:** systemd 255
- **Architecture:** `x86_64`

---

## 3. APU & Compute

### CPU
- **Model:** AMD RYZEN AI MAX+ 395 w/ Radeon 8060S (Strix Halo family)
- **Cores / Threads:** 16 physical cores, 32 hardware threads (1 socket)
- **CPUPower / Scaling Driver:** `amd-pstate-epp`
- **CPU Boost:** Enabled (`/sys/devices/system/cpu/cpufreq/boost` = `1`)
- **Scaling Governor:** `powersave`
- **EPP Setting:** `balance_performance` (available: `default`, `performance`, `balance_performance`, `balance_power`, `power`)
- **Powercap RAPL:** Exposed via `/sys/class/powercap/intel-rapl:0` (`package-0`)

### GPU
- **Model:** AMD Radeon 8060S
- **PCI Address:** `c5:00.0`
- **PCI ID:** `[1002:1586]` (rev c1)
- **Driver:** `amdgpu`
- **Telemetry:** Power input & average (`hwmon8/power1_average`), temperature (`hwmon8/temp1_input`)

---

## 4. Storage Topology

### Primary Internal SSD
- **Model:** `KIOXIA-EXCERIA PLUS G4 SSD` (2.00 TB)
- **Block Device:** `/dev/nvme1n1` (`/dev/nvme1`)
- **Firmware Rev:** `EVFAJ1.2`
- **PCI Address:** `0000:c3:00.0` (`[1e0f:0033]`, rev 01)
- **Current Link Speed:** 16.0 GT/s PCIe (Gen4)
- **Current Link Width:** x4 (Max: x4 at 32.0 GT/s Gen5)
- **Hwmon Sensor:** `hwmon3` (`temp1_input` ~41.8 °C)
- **Role:** Primary system drive (root filesystem `/`)

### Removable Mini SSD
- **Model:** `BIWIN Mini SSD 2TB` (2.05 TB)
- **Block Device:** `/dev/nvme0n1` (`/dev/nvme0`)
- **Firmware Rev:** `BS14552T`
- **PCI Address:** `0000:c4:00.0` (`[1dee:2268]`, rev 03)
- **Current Link Speed:** 16.0 GT/s PCIe (Gen4)
- **Current Link Width:** x2 (Max: x2 at 16.0 GT/s Gen4)
- **Hwmon Sensor:** `hwmon4` (`temp1_input` ~45.8 °C)
- **Role:** Removable secondary storage slot (target of reliability investigation)

---

## 5. Display & Backlight

- **Internal Panel:** Connected on `card1-eDP-1`
- **Native Resolution:** 2880×1800 (supports 120 Hz)
- **Backlight Control:** `/sys/class/backlight/amdgpu_bl1/`
  - Max Brightness: `495000`
  - Current Brightness: `433882` (variable)

---

## 6. Power & Battery

- **Battery Name:** `BAT0` (ACPI `PNP0C0A:00`)
- **Manufacturer:** `Amd Battery`
- **Model Name:** `Li-ion Real Battery`
- **Energy Design:** 85,580,000 µWh (~85.58 Wh)
- **Energy Full:** 80,896,000 µWh (~80.90 Wh)
- **Status:** AC connected (`ACAD`), charging telemetry available in sysfs

---

## 7. Connectivity & Input Peripherals

### USB Topology
- **Bus 003 Device 002:** `1a2c:b001 China Resource Semico Co., Ltd ONE NETBOOK`
  - Internal microcontroller bridging keyboard, gamepad controls, and platform shortcuts.
- **Bus 003 Device 003:** `0e8d:0717 MediaTek Inc. Wireless_Device`
  - MT7925 Wi-Fi 7 + Bluetooth 5.4 module.
  - Driver: `btusb` / `bluetooth` on `hci0`.
- **Bus 003 Device 004:** `2808:5952 FocalTech FocalTech Fingerprint Device`
  - Biometric fingerprint scanner.

---

## 8. Platform Driver Status (`oxpec`)

- **Kernel Module:** `/lib/modules/7.0.0-30-generic/kernel/drivers/platform/x86/oxpec.ko.zst`
- **Driver Description:** `Platform driver that handles EC sensors of OneXPlayer devices`
- **Author:** Joaquín Ignacio Aramendía
- **DMI Alias Match:** `dmi*:rvn*ONE-NETBOOK*:rn*ONEXPLAYER*:` matches modalias `rnONEXPLAYERSUPERX:`.
- **Autoload State:** The driver is present in the Linux kernel tree but was not automatically loaded by udev at initial boot. It can be triggered via `modprobe oxpec` or configured in `/etc/modules-load.d/oxpec.conf`.
- **Hardware Fan Telemetry & Control:** Controlled via `oxpec` hwmon interface once loaded (`pwm1`, `pwm1_enable`).
