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

## Capability inventory template

Fill this from the local Ubuntu Super X before production implementation.

| Capability | Current interface/project | Local status | Super X Helper role |
|---|---|---|---|
| Internal fan telemetry | `oxpec` / hwmon | TBD | Display/normalize |
| Internal fan control | `oxpec` / hwmon | TBD | Safe UI/profile wrapper |
| CPU/package power | RyzenAdj / kernel interfaces | TBD | Normalize validated control |
| CPU boost | TBD | TBD | Optional |
| Charge limit/inhibit | `oxpec`/ACPI if exposed | TBD | Optional |
| Battery telemetry | standard power_supply/UPower | TBD | Display |
| Thermals | hwmon | TBD | Display/policy input |
| Display resolution | compositor/DRM | TBD | Shortcut/profile |
| Refresh rate | compositor/DRM | TBD | Shortcut/profile |
| VRR | compositor/DRM | TBD | Optional |
| RGB | TBD existing project | TBD | Prefer integration |
| Controller | kernel/HHD/InputPlumber | TBD | No duplicate controller stack |
| Gyro | kernel/HHD/InputPlumber | TBD | No duplicate stack unless needed |
| Frost Bay | none known upstream | Missing | Project-owned research/backend |
| Mini SSD diagnostics | PCIe/NVMe standard stack | Available | Project-owned diagnostics |

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

## Items that need current local verification

- [ ] exact Ubuntu/kernel version;
- [ ] whether upstream `oxpec` Super X DMI support is already in the running kernel;
- [ ] exposed `oxpec` fan attributes;
- [ ] battery/charge controls exposed for the Super X mapping;
- [ ] current TDP/power mechanism in use;
- [ ] controller stack and any missing mappings;
- [ ] RGB implementation currently available;
- [ ] display brightness/refresh/VRR behavior;
- [ ] suspend/resume behavior;
- [ ] Bluetooth adapter reliability;
- [ ] Frost Bay device discovery.

Complete this list before committing to the final daemon/UI backend architecture.