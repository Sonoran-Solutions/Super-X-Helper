# Super X Helper — Upstream Controls & Ownership Reference

**Scope:** Phase 2 / SX-002 & SX-CORE-003  
**Status:** Implemented & Verified on ONEXPLAYER Super X (Linux 7.0 / Ubuntu 24.04 LTS)

---

## 1. Upstream Interface Hierarchy & Control Matrix

Super X Helper operates on an **upstream-first policy**:
1. Prefer kernel sysfs/hwmon interfaces where stable.
2. Integrate with maintained handheld userspace daemons (HHD, InputPlumber) rather than duplicating controller mapping stacks.
3. Keep direct EC/BLE manipulation strictly project-owned only for hardware features missing upstream (Frost Bay liquid cooler).

| Hardware Subsystem | Primary Linux Interface | Upstream / Driver | Ownership Boundary | Contention Mitigation |
|---|---|---|---|---|
| **Internal Fans** | `/sys/class/hwmon/hwmon*/pwm1` | `oxpec` (EC driver) | **Super X Helper** owns when manual fan curves are enabled | Read `pwm1_enable` before writing; restore auto mode (`2`) on shutdown |
| **CPU / APU Power** | `amd-pstate-epp` + RAPL (`intel-rapl:0`) | AMD P-State EPP + Powercap | **Shared / Profile-based** | Coordinate with userspace power daemons (power-profiles-daemon / TLP) |
| **CPU Boost** | `/sys/devices/system/cpu/cpufreq/boost` | Linux cpufreq core | **Super X Helper** (Profile toggle) | Read-only observe unless profile explicitly sets boost state |
| **Display / Refresh** | `/sys/class/drm/card1-eDP-1` | `amdgpu` (KMS) | **Desktop Compositor / Steam** | Super X Helper exposes query & shortcuts; compositor owns modesetting |
| **Backlight** | `/sys/class/backlight/amdgpu_bl1/` | `amdgpu` backlight | **Desktop Compositor / Helper** | Standard normalized percentage interface (0.0% – 100.0%) |
| **Input / Gamepad** | `/dev/input/` | Kernel HID / Semico (`1a2c:b001`) | **HHD / InputPlumber / Steam** | **Do NOT reimplement**. Super X Helper coexists and leaves controller mappings to HHD |
| **Frost Bay Cooler** | Bluetooth LE GATT | None upstream (Project-owned) | **Super X Helper Exclusive** | Manages BLE connection, pump/radiator telemetry, and fail-safe safety gates |
| **Mini SSD Reliability** | PCIe sysfs + NVMe subsystem | Linux NVMe driver (`nvme0`) | **Super X Helper Exclusive** | Continuous background link/health classifier without data corruption |

---

## 2. Dynamic Interface Resolution Strategy

**Rule:** Hard-coded paths like `/sys/class/hwmon/hwmon7` are strictly forbidden because hwmon indexing varies dynamically across reboots.

### Hwmon Dynamic Discovery Pattern
In `src/superx_helper/capabilities.py`:
```python
def find_hwmon_by_name(name_query: str, sysfs_hwmon: str = "/sys/class/hwmon") -> Optional[Path]:
    for hw in Path(sysfs_hwmon).glob("hwmon*"):
        name_file = hw / "name"
        if name_file.is_file() and name_file.read_text().strip() == name_query:
            return hw
    return None
```
- Fan control discovers `name == "oxpec"` and resolves `pwm1` and `pwm1_enable`.
- CPU temperatures resolve `name == "k10temp"`.
- GPU telemetry resolves `name == "amdgpu"`.
- NVMe temperatures resolve `name == "nvme"` and cross-check device symlinks against PCI addresses `0000:c3:00.0` and `0000:c4:00.0`.

---

## 3. Contention & Conflict Prevention

Super X Helper monitors for active background daemons:
- `hhd` (Handheld Daemon)
- `inputplumber`
- `power-profiles-daemon`
- `tuned`
- `tlp`

### Ownership States
1. **`UNCONTESTED`**: No conflicting daemon detected. Super X Helper can manage fan curves and power profiles according to user preference.
2. **`COEXISTING`**: HHD or similar handheld daemon detected. Super X Helper yields gamepad/input mapping and reads observed fan/TDP states without overriding unless the user explicitly assigns fan ownership to Super X Helper.
3. **`CONFLICT`**: Conflicting governor or tuning daemon actively overriding parameters. Super X Helper notifies user in the UI and operates in observe-only mode.

---

## 4. Platform Backend Architecture (`src/superx_helper/platform.py`)

Implemented safe control abstraction:
- **No arbitrary writes**: The UI cannot supply raw paths or unvalidated strings.
- **Range checks**:
  - Fan Duty: strictly `0 <= duty <= 100` (maps to `0..255` on `pwm1`).
  - Brightness: strictly `0.0 <= percent <= 100.0` (maps to `0..max_brightness`).
  - EPP: validated against `energy_performance_available_preferences`.
- **Desired vs Observed verification**: Every write reads back the observed sysfs state to verify actuation.
- **Dry-Run Mode**: Enables full simulated testing without privileged access.

---

## 5. Instructions for Next Model Handoff

The next model or agent working on subsequent phases (e.g. Frost Bay BLE reverse engineering or Mini SSD stress qualification) should note:

1. **Test Suite:** Always verify tests with `PYTHONPATH=src python3 -m unittest discover -s tests -p "test_*.py"`.
2. **Read-Only Guarantees:** Do not bypass `PlatformBackend` or `collector.py` to write raw sysfs or EC registers directly.
3. **Host Driver Loading:** On the live Super X host, running `sudo modprobe oxpec` will immediately activate the `oxpec` hwmon node, transitioning `has_fan_control` to `True`.
4. **Frost Bay Protocol Phase:** Follow `docs/FROST_BAY.md`. All BLE work should use passive discovery before any control packet is sent.
5. **Mini SSD Diagnostic Baseline:** Compare any subsequent failure against `docs/snapshots/baseline_snapshot.json` to identify whether the failure is `PCIE_ONLY`, `ABSENT`, or `IO_DEGRADED`.
