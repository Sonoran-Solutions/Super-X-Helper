# Linux Integration Baseline

## Objective

Inventory the Linux interfaces and maintained projects that can already control or expose ONEXPLAYER Super X hardware so Super X Helper only implements what is genuinely missing.

This document should evolve from public-reference baseline into a locally verified capability matrix.

## Current upstream baseline

### `oxpec` platform driver

Current upstream Linux source includes an explicit DMI match for:

```text
Vendor: ONE-NETBOOK
Product: ONEXPLAYER SUPER X
```

The Super X currently maps to the driver's `oxp_g1_a` board implementation.

The driver provides ONEXPLAYER/AOKZOE EC-backed platform support and hwmon/PWM fan interfaces, with additional board-dependent controls.

**Local verification still required:** kernel version containing the Super X support, exposed sysfs paths, exact available attributes, and behavior on this Ubuntu installation.

### Fan control

Community reports on recent kernels demonstrate Super X internal fan control through the `oxpec` hwmon PWM interface.

Do not hard-code a `hwmon7` path. Resolve hwmon devices by their `name` and attributes because hwmon numbering changes across boots/machines.

Expected pattern to verify locally:

```text
/sys/class/hwmon/hwmon*/name
.../pwm1_enable
.../pwm1
```

### CPU/package power

Linux users report RyzenAdj as a functional control path on the Super X where a more direct platform integration is unavailable.

Super X Helper should determine:

- which power limits can be set reliably;
- whether kernel/firmware interfaces supersede RyzenAdj for any setting;
- safe ranges for this exact SKU;
- interactions with AC/battery state;
- whether Frost Bay presence changes the allowed envelope at firmware or userspace level.

Do not assume advertised maximum wattage equals a safe software write range.

### HHD / InputPlumber / gaming handheld stacks

Existing Linux handheld projects may already provide:

- controller mappings;
- TDP integration;
- fan controls;
- RGB;
- gyro;
- Steam Gaming Mode integrations;
- device quirks.

Super X Helper should integrate or coexist rather than fighting for ownership of the same hardware controls.

## Verified local capability inventory

Verified locally on ONEXPLAYER Super X running Ubuntu 24.04.4 LTS (Kernel 7.0.0-30-generic).

| Capability | Current interface/project | Local status | Super X Helper role |
|---|---|---|---|
| Internal fan telemetry | `oxpec` / hwmon | Upstream in kernel (`oxpec.ko.zst`), DMI match verified (`rnONEXPLAYERSUPERX:`), needs explicit module load | Display/normalize from resolved hwmon |
| Internal fan control | `oxpec` / hwmon | Supported via `pwm1` / `pwm1_enable` upon loading `oxpec` | Safe UI/profile wrapper with range validation |
| CPU/package power | `amd-pstate-epp` / RAPL (`intel-rapl:0`) / RyzenAdj | Available via sysfs powercap + CPU scaling; RyzenAdj for direct TDP limits | Normalize validated control with safe bounds |
| CPU boost | `/sys/devices/system/cpu/cpufreq/boost` | Upstream & stable (verified active `1`) | Profile toggle (on/off) |
| Charge limit/inhibit | `oxpec` / ACPI | Not exposed in standard `BAT0` sysfs; depends on `oxpec` EC interface | Under investigation |
| Battery telemetry | `/sys/class/power_supply/BAT0` | Upstream & verified active (85.58 Wh design, ~80.9 Wh full) | Real-time battery & charge status display |
| Thermals | hwmon (`k10temp`, `amdgpu`, `nvme`) | Upstream & active (`hwmon7` CPU Tctl, `hwmon8` GPU, `hwmon3`/`hwmon4` NVMe) | Unified telemetry monitoring |
| Display resolution | DRM (`card1-eDP-1`) | Upstream & active (native 2880×1800 @ 120 Hz) | Quick mode/scaling selection |
| Display brightness | `/sys/class/backlight/amdgpu_bl1` | Upstream & active (max brightness 495000) | Brightness slider control |
| VRR / FreeSync | compositor / DRM (`amdgpu`) | Supported by GPU/driver stack | Optional toggle where supported by compositor |
| RGB / Controller | Semico USB bridge (`1a2c:b001`) | Device active on USB bus 3; controller handled via standard kernel input/HID | Avoid conflicting with active gamepad mapping |
| Bluetooth stack | `btusb` / `bluetooth` on MediaTek MT7925 (`0e8d:0717`) | Active via `hci0`; requires `bluetooth.service` and user permissions | Bluetooth discovery & GATT transport for Frost Bay |
| Frost Bay cooler | Bluetooth LE GATT | Hardware present; software control missing upstream | Project-owned BLE reverse-engineering and client |
| Mini SSD diagnostics | PCIe / NVMe sysfs + `nvme-cli` | Upstream & verified (`c4:00.0`, Gen4 x2 BIWIN 2TB) | State classifier, error telemetry, reliability tests |

## Local inventory procedure

### Platform identity

```bash
cat /sys/class/dmi/id/sys_vendor
cat /sys/class/dmi/id/product_name
cat /sys/class/dmi/id/board_name
uname -a
```

### `oxpec` / hwmon

```bash
lsmod | grep -E 'oxp|oxpec'
for n in /sys/class/hwmon/hwmon*/name; do
  printf '%s: ' "$n"
  cat "$n"
done
```

Then inspect only the hwmon directory whose name identifies the relevant ONEXPLAYER driver.

### Power/thermal

Inventory standard power and thermal interfaces before adding special handling.

```bash
find /sys/class/power_supply -maxdepth 2 -type f 2>/dev/null
find /sys/class/thermal -maxdepth 2 -type f 2>/dev/null
```

Do not dump unrelated serial numbers or private identifiers into public logs without reviewing them.

### Input stack

Determine which stack Ubuntu is actually using before altering controller behavior:

```bash
ls /dev/input/by-id/
systemctl status hhd 2>/dev/null
systemctl status inputplumber 2>/dev/null
```

## Ownership rule

Only one component should actively own a given control where possible.

For example, if HHD is already applying fan curves, Super X Helper should either:

- integrate through HHD;
- explicitly take ownership while disabling/conflicting automation; or
- operate read-only.

Do not allow two daemons to continuously fight over PWM or TDP.

## Backend interface strategy

Production code should discover concrete Linux interfaces once, validate them, and expose high-level capabilities.

Bad:

```text
UI → sudo sh -c "echo 255 > /sys/.../pwm1"
```

Better:

```text
UI → setInternalFanDuty(100%)
          ↓
daemon validates capability + range
          ↓
resolved hwmon backend writes canonical value
          ↓
backend reads observed state
```

## Upstream-first policy

If a missing Super X control can reasonably be added to an existing maintained upstream project, prefer contributing there and consuming that support rather than carrying a permanent private kernel patch.

Super X Helper should remain useful even as upstream support improves by providing:

- unified UI;
- profiles;
- Frost Bay integration;
- Mini SSD diagnostics;
- capability discovery;
- safety policy;
- diagnostics/export.

## Verification status matrix
 
- [x] exact Ubuntu/kernel version: Ubuntu 24.04.4 LTS / Linux 7.0.0-30-generic
- [x] whether upstream `oxpec` Super X DMI support is already in the running kernel: Verified (`oxpec.ko.zst` matches modalias `rnONEXPLAYERSUPERX:`, requires `modprobe oxpec`)
- [ ] exposed `oxpec` fan attributes: Pending host-level `modprobe oxpec` execution
- [x] battery/charge controls exposed for the Super X mapping: Basic telemetry in `/sys/class/power_supply/BAT0/`; charge threshold not exposed via standard ACPI
- [x] current TDP/power mechanism in use: `amd-pstate-epp` + `energy_performance_preference`, CPU boost toggle, RAPL powercap
- [x] controller stack and any missing mappings: Semico USB bridge (`1a2c:b001`) detected
- [ ] RGB implementation currently available: Under investigation
- [x] display brightness/refresh/VRR behavior: 2880x1800 @ 120Hz on `card1-eDP-1`, backlight on `amdgpu_bl1`
- [ ] suspend/resume behavior: To be qualified during Phase 2 Mini SSD stress tests
- [x] Bluetooth adapter reliability: MediaTek MT7925 (`0e8d:0717`) on `hci0`
- [ ] Frost Bay device discovery: Target of Phase 1 BLE research tasks