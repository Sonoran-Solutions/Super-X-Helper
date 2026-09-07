# Live Integration Handoff — ONEXPLAYER Super X

**Date:** 2026-09-07
**Machine:** ONEXPLAYER Super X (board `onec1`, BIOS `V1.01`), Ubuntu 24.04.4 LTS / kernel `7.0.0-30-generic`.
**Session privilege:** unprivileged user (`uid 1000`). `sudo` requires a password; no non-interactive root was available and approval prompts were disabled. This constrains the write-validation result below.

This pass completed ordinary Linux integration review + UI/service corrections and refreshed the live read-only baseline. It did **not** begin Frost Bay protocol work or Mini SSD stress/root-cause experiments.

---

## Confirmed live read capabilities

Directly observed on the current machine (fresh capture):

- **Identity/firmware:** `ONE-NETBOOK` / `ONEXPLAYER SUPER X`, board `onec1`, BIOS `V1.01` (2026-01-06).
- **OS/kernel:** Ubuntu 24.04.4 LTS (`noble`), kernel `7.0.0-30-generic` (x86_64).
- **APU/CPU:** AMD RYZEN AI MAX+ 395, 32 logical threads; `amd-pstate-epp` active on all 32 policies; governor `powersave`; EPP `balance_performance`; CPU boost **enabled**.
- **Backlight:** `amdgpu_bl1`; `max_brightness` 495000; `actual_brightness` 433882 (**87.7%**); requested `brightness` 460697 (**93.1%**). The requested-vs-actual gap is noted for future brightness validation.
- **Battery:** `BAT0` present, `Not charging`, 99 %, 79.93 Wh / 80.9 Wh (design 85.58 Wh).
- **hwmon devices:** `acpitz`, `BAT0`, `nvme` (x2), `mt7925_phy0`, `k10temp` (Tctl 61.1 °C), `amdgpu` (edge 51.0 °C, PPT 30 W). **No `oxp_ec`/`oxpec` hwmon.**
- **Displays:** `card1-eDP-1` connected 2880×1800 (internal); `card1-HDMI-A-1` connected 3840×2160 (external — new vs. the original baseline, which recorded only the internal panel).
- **Storage:** BIWIN Mini SSD `nvme0` (`1dee:2268`) Gen4 x2 → `NVME_PRESENT`; KIOXIA internal `nvme1` (`1e0f:0033`) Gen4 x4. Mini SSD reliability `NOT_QUALIFIED`.
- **Connectivity:** 1 Bluetooth adapter (`hci0`); 0 cached Frost-Bay-like devices (collector does not scan).
- **Capability snapshot:** 15 records; **zero** `can_write`; Frost Bay telemetry/control `RESEARCH_PENDING`/`BLOCKED`; Mini SSD reliability `NOT_QUALIFIED`.

The environment is materially consistent with `docs/local-hardware-baseline.md`; the only new observations are the connected external HDMI display and the KIOXIA PCI ID `1e0f:0033` (both recorded below rather than silently replacing prior evidence).

---

## Newly production-qualified writes

**None.**

No reversible write experiment was performed, so no capability passes the research-to-production gate. The reason is environmental, not code-path: all candidate write interfaces are root-owned and this session could not obtain root:

```text
/sys/devices/system/cpu/cpufreq/boost                         -rw-r--r-- root root
/sys/devices/system/cpu/cpufreq/policy0/energy_performance_preference  -rw-r--r-- root root
/sys/class/backlight/amdgpu_bl1/brightness                    -rw-r--r-- root root
```

`sudo -n true` → "a password is required". Loading `oxpec` (modprobe) is likewise a root operation. Per the hard-stop rules, no write was attempted without a demonstrated rollback path and root authorization.

---

## Still-unverified ordinary features

| Feature | Reason still blocked |
|---|---|
| CPU EPP write | Read path confirmed (`balance_performance`); write is root-only and was not exercised. |
| CPU boost write | Read path confirmed (enabled); write is root-only and was not exercised. |
| Display brightness write | Read path confirmed (87.7 % actual / 93.1 % requested); sysfs write is root-only; requested-vs-actual discrepancy and possible compositor/logind ownership need investigation. |
| Internal fan | `oxpec` installed but does **not** match the Super X (see below); no live `oxp_ec` hwmon exists; fan write remains `SUPPORTED_UNVERIFIED`. |
| Power target | No production-selected APU power-target write path; powercap/RAPL read path only. |
| Charge limit/bypass | No trustworthy interface validated; remains `UNAVAILABLE` in the contract (although upstream `oxpec` *would* expose `oxp-charge-control` for `oxp_g1_a`, this is not live-verified here). |
| RGB / controller integration | No maintained/selected path; unchanged. |

---

## `oxpec` result

**Exact module/hwmon state:** module installed but **not loaded**; **no `oxp_ec`/`oxpec` hwmon device exists** on the running kernel.

Evidence gathered read-only:

- Module file present: `/lib/modules/7.0.0-30-generic/kernel/drivers/platform/x86/oxpec.ko.zst` (in-tree, GPL).
- `modinfo oxpec` DMI alias inventory contains `ONEXPLAYER G1 A`, `ONEXPLAYER G1 i`, and a generic `ONEXPLAYER` alias, but **no `ONEXPLAYER SUPER X` entry**.
- Module strings contain no "ONEXPLAYER SUPER X" board name; the generic `ONEXPLAYER` alias is the space-stripped modalias of the legacy `ONE XPLAYER` board (mapped to `oxp_mini_amd`).
- Upstream evidence ([commit `0b6573e`](https://github.com/torvalds/linux/commit/0b6573e23acc7bca808e539e3edea49683f106de), "platform/x86: oxpec: add support for OneXPlayer Super X", 2026-06): *"Current mainline oxpec does not contain a matching DMI entry for this system, so the in-tree driver is not auto-loaded. The tested Super X fan, PWM, turbo-toggle, and battery charge-control EC layout matches the existing ONEXPLAYER G1 A handling."* It maps Super X → `oxp_g1_a`.

**Conclusion:** the installed kernel's `oxpec` does not support the Super X. `dmi_first_match` would return no match for board name "ONEXPLAYER SUPER X", so module init would return `-ENODEV` (no hwmon exposed). Fan telemetry/control semantics are therefore **not sufficiently established** for this host, and a fan write must not be attempted.

**Recommendation:** update/backport the kernel module to include the Super X quirk (or upgrade to a kernel containing it), then re-run under a root session to confirm the `oxp_ec` hwmon (`fan1_input` = RPM, `pwm1`, `pwm1_enable`) before any fan write.

For reference, the upstream `oxpec` semantics for `oxp_g1_a` (from source, not live-verified here) are: `fan1_input` from EC reg `0x76` (2 bytes), `pwm1` from reg `0x4B`, `pwm1_enable` from reg `0x4A`; PWM range 0–255 with **no** scaling; `pwm1_enable` 0 = full speed, 1 = manual, 2 = auto; plus a `tt_toggle` platform attribute and `oxp-charge-control` charge-limit/bypass extension. These are **upstream/source expectations only** — they do not qualify any live write.

---

## UI/service corrections

### Frost Bay state semantics
- `FrostBayResearchCard` no longer maps `CapabilityStatus.CONFIRMED_LOCAL` to "Connected". A future validated Frost Bay capability renders "Locally Validated" and never asserts connection/health state.
- The pre-research fallback text ("protocol/health semantics not validated") is now scoped to `RESEARCH_PENDING` only; a validated capability gets a neutral validation description instead. Pre-research state stays visually `RESEARCH_PENDING` / `BLOCKED`.

### Profile placeholders
- `ProfilesPage` now uses intent-only descriptions ("Intent: prioritize lower fan noise. Fan/power policy not yet defined."). Removed "reduced/automatic/aggressive fan curve" and wattage-envelope claims.

### Structured value formatting
- `format_observed_value` now dispatches on stable `capability_id` first (battery / display / Mini SSD), then validates the expected data shape. It no longer treats every list as display telemetry or every `state` dict as Mini SSD data.

### Service architecture preparation
- Moved `OperationResult` into `contracts.py` so the transport/D-Bus boundary does not import the platform backend.
- Added `SuperXService.set_capability(capability_id, value)` — typed, capability-scoped, service-side authorization, fail-closed for unknown/unauthorized/read-only capabilities.
- Aligned `PlatformBackend` write-authorization keys to the stable `CapabilityId` values (previously they were ad-hoc strings like `"fan_control"`, `"epp"`, `"backlight"`).
- Extended `ServiceClient` protocol and `LocalServiceClient` with `set_capability`.
- Added `transport.py` with thin `snapshot`/`record`/`operation_result` serialization (no duplicated capability semantics; `can_write` is re-derived, never round-tripped).
- Fixed fan hwmon discovery: the driver registers its hwmon as **`oxp_ec`** (not `oxpec`); `detect_capabilities` now matches `oxp_ec` with a legacy `oxpec` fallback.

The UI remains unprivileged and imports no raw hardware backends. No system-wide D-Bus/polkit/service files were installed (deferred until live write validation exists).

### Tests
- Suite grew from 31 to **45 passing tests**. New coverage asserts rendered text/state (not just widget construction): Frost Bay validated-vs-research-pending wording, profile intent-only text, capability-id-driven value formatting, service mutation dispatch/authorization/type validation, transport round-trips, and `oxp_ec` hwmon name matching.

---

## Recommended next task

Run the same repo under a **root session (sudo)** on this Super X, in this order:

1. Confirm/install a kernel whose `oxpec` includes the Super X quirk (commit `0b6573e`), then `modprobe oxpec` and inventory the `oxp_ec` hwmon (`name`, `fan1_input`, `pwm1`, `pwm1_enable`, `tt_toggle`, `oxp-charge-control`).
2. Perform single-step reversible write validation: **EPP → CPU boost → brightness**, each with before/read-back/restore/verify, before any fan write.
3. Fan write only after step 1 confirms `oxp_ec` semantics; never test zero duty, never disable thermal protection, never pair with increased TDP.
4. Keep Frost Bay `RESEARCH_PENDING` and Mini SSD `NOT_QUALIFIED`; do not begin those research tracks until the pre-Astra daily-driver gate passes.
