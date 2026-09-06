#!/usr/bin/env python3
"""Read-only diagnostic collector for the ONEXPLAYER Super X.

The default collector does not change hardware state, start Bluetooth scans, or
run storage writes.  Public output redacts unique device identifiers unless the
operator explicitly opts in.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from superx_helper.storage import discover_mini_ssd, list_nvme_namespaces, rooted

CommandRunner = Callable[[Sequence[str]], Tuple[int, str, str]]
_RELEVANT_KERNEL = re.compile(r"\b(nvme|pcie|aer|oxpec|amdgpu|bluetooth|btusb)\b", re.I)
_FROST_BAY_NAME = re.compile(r"(frost|coolingsystem|once\d*|onex.*cool)", re.I)


def _read_sysfs_text(path: str | Path) -> Optional[str]:
    try:
        p = Path(path)
        if p.exists() and p.is_file():
            return p.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        pass
    return None


def _read_sysfs_int(path: str | Path) -> Optional[int]:
    value = _read_sysfs_text(path)
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _run_command(argv: Sequence[str], timeout: int = 5) -> Tuple[int, str, str]:
    executable = shutil.which(argv[0])
    if not executable:
        return 127, "", f"{argv[0]} unavailable"
    try:
        proc = subprocess.run(
            [executable, *argv[1:]],
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
        return proc.returncode, proc.stdout, proc.stderr
    except (OSError, subprocess.SubprocessError) as exc:
        return 126, "", str(exc)


def _redacted(value: Optional[str], include_identifiers: bool) -> Optional[str]:
    if value is None:
        return None
    return value if include_identifiers else "REDACTED"


def get_dmi_info(base_path: str = "/sys/class/dmi/id") -> Dict[str, Any]:
    fields = [
        "sys_vendor",
        "product_name",
        "product_version",
        "board_vendor",
        "board_name",
        "board_version",
        "bios_vendor",
        "bios_version",
        "bios_date",
        "chassis_type",
        "modalias",
    ]
    return {field: _read_sysfs_text(Path(base_path) / field) for field in fields}


def get_os_kernel_info() -> Dict[str, Any]:
    os_info: Dict[str, Any] = {
        "kernel_release": None,
        "kernel_version": None,
        "os_name": None,
        "os_version": None,
        "os_id": None,
    }
    try:
        uname = os.uname()
        os_info.update(
            kernel_release=uname.release,
            kernel_version=uname.version,
            architecture=uname.machine,
        )
    except OSError:
        pass

    release = _read_sysfs_text("/etc/os-release")
    if release:
        for line in release.splitlines():
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            value = value.strip('"\'')
            if key == "NAME":
                os_info["os_name"] = value
            elif key == "VERSION":
                os_info["os_version"] = value
            elif key == "ID":
                os_info["os_id"] = value
    return os_info


def get_cpu_info() -> Dict[str, Any]:
    cpu: Dict[str, Any] = {
        "model_name": None,
        "logical_cores": os.cpu_count() or 0,
        "scaling_driver": _read_sysfs_text("/sys/devices/system/cpu/cpufreq/policy0/scaling_driver"),
        "scaling_governor": _read_sysfs_text("/sys/devices/system/cpu/cpufreq/policy0/scaling_governor"),
        "epp": _read_sysfs_text("/sys/devices/system/cpu/cpufreq/policy0/energy_performance_preference"),
        "epp_available": _read_sysfs_text("/sys/devices/system/cpu/cpufreq/policy0/energy_performance_available_preferences"),
        "boost_enabled": _read_sysfs_int("/sys/devices/system/cpu/cpufreq/boost"),
    }
    cpuinfo = _read_sysfs_text("/proc/cpuinfo")
    if cpuinfo:
        for line in cpuinfo.splitlines():
            if line.startswith("model name"):
                cpu["model_name"] = line.split(":", 1)[1].strip()
                break
    return cpu


def get_battery_info(base_path: str = "/sys/class/power_supply/BAT0") -> Dict[str, Any]:
    bat_path = Path(base_path)
    if not bat_path.exists():
        return {"present": False}

    energy_now = _read_sysfs_int(bat_path / "energy_now")
    energy_full = _read_sysfs_int(bat_path / "energy_full")
    energy_design = _read_sysfs_int(bat_path / "energy_full_design")
    voltage = _read_sysfs_int(bat_path / "voltage_now")
    return {
        "present": _read_sysfs_int(bat_path / "present") == 1,
        "status": _read_sysfs_text(bat_path / "status"),
        "capacity_pct": _read_sysfs_int(bat_path / "capacity"),
        "manufacturer": _read_sysfs_text(bat_path / "manufacturer"),
        "model_name": _read_sysfs_text(bat_path / "model_name"),
        "energy_now_wh": round(energy_now / 1e6, 2) if energy_now is not None else None,
        "energy_full_wh": round(energy_full / 1e6, 2) if energy_full is not None else None,
        "energy_design_wh": round(energy_design / 1e6, 2) if energy_design is not None else None,
        "voltage_now_v": round(voltage / 1e6, 2) if voltage is not None else None,
    }


def get_hwmon_info(sysfs_hwmon: str = "/sys/class/hwmon") -> List[Dict[str, Any]]:
    sensors: List[Dict[str, Any]] = []
    base = Path(sysfs_hwmon)
    if not base.exists():
        return sensors

    for hw in sorted(base.glob("hwmon*")):
        name = _read_sysfs_text(hw / "name") or hw.name
        readings: Dict[str, Any] = {}
        for temp_input in sorted(hw.glob("temp*_input")):
            prefix = temp_input.name.replace("_input", "")
            raw = _read_sysfs_int(temp_input)
            label = _read_sysfs_text(hw / f"{prefix}_label") or prefix
            readings[label] = {"temp_c": round(raw / 1000.0, 1) if raw is not None else None}
        for fan_input in sorted(hw.glob("fan*_input")):
            prefix = fan_input.name.replace("_input", "")
            label = _read_sysfs_text(hw / f"{prefix}_label") or prefix
            readings[label] = {"rpm": _read_sysfs_int(fan_input)}
        for pwm in sorted(hw.glob("pwm*")):
            if pwm.is_file() and not pwm.name.endswith("_enable"):
                readings[pwm.name] = {
                    "duty": _read_sysfs_int(pwm),
                    "enable_mode": _read_sysfs_int(hw / f"{pwm.name}_enable"),
                }
        for power_input in sorted(hw.glob("power*_input")):
            prefix = power_input.name.replace("_input", "")
            raw = _read_sysfs_int(power_input)
            label = _read_sysfs_text(hw / f"{prefix}_label") or prefix
            readings[label] = {"watts": round(raw / 1e6, 2) if raw is not None else None}
        sensors.append({"id": hw.name, "name": name, "readings": readings})
    return sensors


def get_display_info(
    drm_path: str = "/sys/class/drm",
    backlight_path: str = "/sys/class/backlight",
) -> Dict[str, Any]:
    display: Dict[str, Any] = {"connectors": [], "backlight": {}}
    drm = Path(drm_path)
    if drm.exists():
        for connector in sorted(drm.glob("card*-*")):
            status = _read_sysfs_text(connector / "status")
            if status != "connected":
                continue
            modes = [
                item.strip()
                for item in (_read_sysfs_text(connector / "modes") or "").splitlines()
                if item.strip()
            ]
            display["connectors"].append(
                {
                    "connector": connector.name,
                    "status": status,
                    "modes": modes[:10],
                    "primary_mode": modes[0] if modes else None,
                }
            )

    backlights = Path(backlight_path)
    if backlights.exists():
        for backlight in backlights.iterdir():
            actual = _read_sysfs_int(backlight / "actual_brightness")
            max_value = _read_sysfs_int(backlight / "max_brightness")
            percent = (
                round((actual / max_value) * 100, 1)
                if actual is not None and max_value not in (None, 0)
                else None
            )
            display["backlight"][backlight.name] = {
                "actual": actual,
                "max": max_value,
                "percent": percent,
            }
    return display


def _find_pci_parent(path: Path) -> Optional[Path]:
    for candidate in [path, *path.parents]:
        if (candidate / "vendor").exists() and (candidate / "device").exists():
            return candidate
    return None


def _get_nvme_smart(
    controller: str,
    runner: CommandRunner = _run_command,
    *,
    enabled: bool = True,
) -> Dict[str, Any]:
    if not enabled:
        return {"available": False, "reason": "external command collection disabled"}
    code, stdout, stderr = runner(["nvme", "smart-log", f"/dev/{controller}", "-o", "json"])
    if code != 0:
        return {"available": False, "reason": (stderr.strip() or f"nvme exited {code}")[:240]}
    try:
        raw = json.loads(stdout)
    except json.JSONDecodeError:
        return {"available": False, "reason": "nvme smart-log returned invalid JSON"}

    allowed = [
        "critical_warning",
        "temperature",
        "available_spare",
        "available_spare_threshold",
        "percentage_used",
        "data_units_read",
        "data_units_written",
        "host_read_commands",
        "host_write_commands",
        "controller_busy_time",
        "power_cycles",
        "power_on_hours",
        "unsafe_shutdowns",
        "media_errors",
        "num_err_log_entries",
        "warning_temp_time",
        "critical_comp_time",
    ]
    return {"available": True, **{key: raw.get(key) for key in allowed if key in raw}}


def get_storage_inventory(
    sysfs_root: str = "",
    *,
    include_identifiers: bool = False,
    runner: CommandRunner = _run_command,
) -> Dict[str, Any]:
    controllers: List[Dict[str, Any]] = []
    nvme_root = rooted(sysfs_root, "/sys/class/nvme")
    mini = discover_mini_ssd(sysfs_root)

    if nvme_root.exists():
        for ctrl in sorted(nvme_root.glob("nvme*")):
            if not re.fullmatch(r"nvme\d+", ctrl.name):
                continue
            model = _read_sysfs_text(ctrl / "model")
            serial = _read_sysfs_text(ctrl / "serial")
            firmware = _read_sysfs_text(ctrl / "firmware_rev")
            resolved_ctrl = ctrl.resolve()
            namespaces = list_nvme_namespaces(resolved_ctrl, ctrl.name, sysfs_root)

            pci = _find_pci_parent((ctrl / "device").resolve()) if (ctrl / "device").exists() else None
            pci_address = pci.name if pci else None
            vendor = _read_sysfs_text(pci / "vendor") if pci else None
            device = _read_sysfs_text(pci / "device") if pci else None
            vendor_device = None
            if vendor and device:
                vendor_device = f"{vendor.removeprefix('0x')}:{device.removeprefix('0x')}"

            is_mini = pci_address == mini.pci_address or "BIWIN" in (model or "").upper()
            classification = mini.state.value if is_mini else ("NVME_PRESENT" if namespaces else "PCIE_ONLY")
            controllers.append(
                {
                    "controller": ctrl.name,
                    "model": model,
                    "serial": _redacted(serial, include_identifiers),
                    "firmware_rev": firmware,
                    "is_removable_mini_ssd": is_mini,
                    "classification": classification,
                    "pci": {
                        "address": pci_address,
                        "vendor_device": vendor_device,
                        "link_speed": _read_sysfs_text(pci / "current_link_speed") if pci else None,
                        "link_width": _read_sysfs_int(pci / "current_link_width") if pci else None,
                        "max_link_speed": _read_sysfs_text(pci / "max_link_speed") if pci else None,
                        "max_link_width": _read_sysfs_int(pci / "max_link_width") if pci else None,
                    },
                    "namespaces": namespaces,
                    "smart": _get_nvme_smart(ctrl.name, runner, enabled=not bool(sysfs_root)),
                }
            )

    mini_dict = mini.to_dict()
    mini_dict["reliability"] = "NOT_QUALIFIED"
    return {"controllers": controllers, "count": len(controllers), "mini_ssd": mini_dict}


def get_connectivity_inventory(
    *,
    include_identifiers: bool = False,
    runner: CommandRunner = _run_command,
    sysfs_root: str = "",
) -> Dict[str, Any]:
    adapters = []
    bt_path = rooted(sysfs_root, "/sys/class/bluetooth")
    if bt_path.exists():
        for hci in sorted(bt_path.glob("hci*")):
            address = _read_sysfs_text(hci / "address")
            adapters.append(
                {
                    "name": hci.name,
                    "address": _redacted(address, include_identifiers) if address else "present",
                }
            )

    target_devices: List[Dict[str, Any]] = []
    if not sysfs_root:
        code, stdout, _ = runner(["bluetoothctl", "devices"])
        if code == 0:
            for line in stdout.splitlines():
                match = re.match(r"Device\s+([0-9A-Fa-f:]{17})\s+(.+)$", line.strip())
                if not match:
                    continue
                address, name = match.groups()
                if not _FROST_BAY_NAME.search(name):
                    continue
                info_code, info, _ = runner(["bluetoothctl", "info", address])
                uuids = []
                connected = None
                paired = None
                if info_code == 0:
                    for info_line in info.splitlines():
                        stripped = info_line.strip()
                        if stripped.startswith("UUID:"):
                            uuids.append(stripped.removeprefix("UUID:").strip())
                        elif stripped.startswith("Connected:"):
                            connected = stripped.split(":", 1)[1].strip().lower() == "yes"
                        elif stripped.startswith("Paired:"):
                            paired = stripped.split(":", 1)[1].strip().lower() == "yes"
                target_devices.append(
                    {
                        "name": name,
                        "address": _redacted(address, include_identifiers),
                        "connected": connected,
                        "paired": paired,
                        "service_uuids": uuids,
                        "source": "cached BlueZ device list; no scan started",
                    }
                )

    usb_devices = []
    usb_root = rooted(sysfs_root, "/sys/bus/usb/devices")
    if usb_root.exists():
        for dev in sorted(usb_root.glob("*")):
            vendor = _read_sysfs_text(dev / "idVendor")
            product = _read_sysfs_text(dev / "idProduct")
            if vendor and product and f"{vendor}:{product}" in {
                "1a2c:b001",
                "0e8d:0717",
                "2808:5952",
            }:
                usb_devices.append(
                    {
                        "dev": dev.name,
                        "vid_pid": f"{vendor}:{product}",
                        "manufacturer": _read_sysfs_text(dev / "manufacturer"),
                        "product": _read_sysfs_text(dev / "product"),
                    }
                )

    return {
        "bluetooth_adapters": adapters,
        "frost_bay_candidates": target_devices,
        "bluetooth_note": "Cached target-like devices only; collector does not start a Bluetooth scan.",
        "known_platform_peripherals": usb_devices,
    }


def get_kernel_messages(runner: CommandRunner = _run_command) -> Dict[str, Any]:
    code, stdout, stderr = runner(["journalctl", "-k", "-o", "cat", "--no-pager", "-n", "500"])
    if code != 0:
        return {"available": False, "reason": (stderr.strip() or f"journalctl exited {code}")[:240], "lines": []}
    lines = [line for line in stdout.splitlines() if _RELEVANT_KERNEL.search(line)]
    return {"available": True, "lines": lines[-200:]}


def get_platform_module_status(sysfs_root: str = "") -> Dict[str, Any]:
    modules_loaded: List[str] = []
    modules_path = rooted(sysfs_root, "/proc/modules")
    text = _read_sysfs_text(modules_path)
    if text:
        modules_loaded = [line.split()[0] for line in text.splitlines() if line.split()]

    if sysfs_root:
        module_path = rooted(sysfs_root, "/lib/modules/oxpec.ko.zst")
    else:
        module_path = Path(
            f"/lib/modules/{os.uname().release}/kernel/drivers/platform/x86/oxpec.ko.zst"
        )
    return {
        "oxpec_loaded": "oxpec" in modules_loaded,
        "oxpec_module_available": module_path.exists(),
        "oxpec_module_path": str(module_path) if module_path.exists() else None,
        "amdgpu_loaded": "amdgpu" in modules_loaded,
        "btusb_loaded": "btusb" in modules_loaded,
    }


def collect_all(*, include_identifiers: bool = False) -> Dict[str, Any]:
    from superx_helper.capabilities import detect_capabilities

    return {
        "schema_version": 2,
        "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "privacy": {"unique_identifiers_included": include_identifiers},
        "dmi": get_dmi_info(),
        "os_kernel": get_os_kernel_info(),
        "cpu": get_cpu_info(),
        "battery": get_battery_info(),
        "display": get_display_info(),
        "storage": get_storage_inventory(include_identifiers=include_identifiers),
        "thermal_sensors": get_hwmon_info(),
        "connectivity": get_connectivity_inventory(include_identifiers=include_identifiers),
        "kernel_messages": get_kernel_messages(),
        "platform_modules": get_platform_module_status(),
        "capabilities": detect_capabilities().to_dict(),
    }


def format_summary(data: Dict[str, Any]) -> str:
    dmi = data.get("dmi", {})
    cpu = data.get("cpu", {})
    os_info = data.get("os_kernel", {})
    storage = data.get("storage", {})
    battery = data.get("battery", {})
    display = data.get("display", {})
    modules = data.get("platform_modules", {})
    capabilities = data.get("capabilities", {})

    lines = [
        "============================================================",
        "          ONEXPLAYER Super X — Diagnostic Baseline          ",
        "============================================================",
        f"Timestamp (UTC): {data.get('timestamp_utc')}",
        "",
        "--- [1. Device & Firmware Identity] ---",
        f"Vendor / Product: {dmi.get('sys_vendor')} / {dmi.get('product_name')}",
        f"Board / Version : {dmi.get('board_name')} (rev {dmi.get('board_version')})",
        f"BIOS            : {dmi.get('bios_version')} ({dmi.get('bios_date')}) by {dmi.get('bios_vendor')}",
        "",
        "--- [2. OS & Platform Kernel] ---",
        f"OS              : {os_info.get('os_name')} {os_info.get('os_version')}",
        f"Kernel          : {os_info.get('kernel_release')}",
        f"oxpec Driver    : {'LOADED' if modules.get('oxpec_loaded') else 'AVAILABLE (Not Loaded)'} [Module: {modules.get('oxpec_module_available')}]",
        "",
        "--- [3. APU & CPU Scaling] ---",
        f"CPU Model       : {cpu.get('model_name')}",
        f"Topology        : {cpu.get('logical_cores')} logical threads",
        f"Scaling Driver  : {cpu.get('scaling_driver')} (Governor: {cpu.get('scaling_governor')})",
        f"EPP Preference  : {cpu.get('epp')} (Boost: {'Enabled' if cpu.get('boost_enabled') == 1 else 'Disabled'})",
        "",
        "--- [4. Storage Topology] ---",
    ]

    for ctrl in storage.get("controllers", []):
        pci = ctrl.get("pci", {})
        tag = "[MINI SSD]" if ctrl.get("is_removable_mini_ssd") else "[INTERNAL SSD]"
        lines.append(f"{tag} {ctrl.get('model')} ({ctrl.get('controller')}, FW: {ctrl.get('firmware_rev')})")
        lines.append(
            f"   PCI Slot: {pci.get('address')} ({pci.get('vendor_device')}) | "
            f"Link: {pci.get('link_speed')} x{pci.get('link_width')} (Max: {pci.get('max_link_speed')} x{pci.get('max_link_width')})"
        )
        lines.append(
            f"   State Classification: {ctrl.get('classification')} | Block Devices: {', '.join(ctrl.get('namespaces', [])) or 'none detected'}"
        )
        smart = ctrl.get("smart", {})
        if smart.get("available"):
            lines.append(
                f"   SMART: critical_warning={smart.get('critical_warning')} media_errors={smart.get('media_errors')} error_entries={smart.get('num_err_log_entries')}"
            )

    mini = storage.get("mini_ssd", {})
    lines.append(f"Mini SSD Reliability: {mini.get('reliability', 'NOT_QUALIFIED')}")

    lines.extend(["", "--- [5. Thermals & Power] ---"])
    for sensor in data.get("thermal_sensors", []):
        readings = sensor.get("readings", {})
        values = []
        for label, reading in readings.items():
            if reading.get("temp_c") is not None:
                values.append(f"{label}: {reading['temp_c']}°C")
            if reading.get("watts") is not None:
                values.append(f"{label}: {reading['watts']}W")
        if values:
            lines.append(f"  {sensor.get('name')} ({sensor.get('id')}): {', '.join(values)}")
    lines.append(
        f"Battery Status  : {battery.get('status')} ({battery.get('capacity_pct')}%) | "
        f"Capacity: {battery.get('energy_now_wh')} Wh / {battery.get('energy_full_wh')} Wh (Design: {battery.get('energy_design_wh')} Wh)"
    )

    lines.extend(["", "--- [6. Display & Peripherals] ---"])
    for connector in display.get("connectors", []):
        lines.append(
            f"Display Output  : {connector.get('connector')} [{connector.get('status')}] - Mode: {connector.get('primary_mode')}"
        )
    for name, backlight in display.get("backlight", {}).items():
        lines.append(f"Backlight       : {name} at {backlight.get('percent')}%")
    connectivity = data.get("connectivity", {})
    lines.append(f"Bluetooth       : {len(connectivity.get('bluetooth_adapters', []))} adapter(s) found")
    lines.append(f"Frost Bay cached candidates: {len(connectivity.get('frost_bay_candidates', []))}")

    lines.extend(["", "--- [7. Capability Discovery] ---"])
    lines.append(f"Ownership State : {capabilities.get('ownership_state')}")
    fan_status = (
        f"Interface present ({capabilities.get('fan_hwmon_name')}); write validation still required"
        if capabilities.get("has_fan_control")
        else ("Module available; live hwmon unverified" if capabilities.get("oxpec_driver_available") else "Unavailable")
    )
    lines.append(f"Fan Interface   : {fan_status}")
    lines.append(
        f"CPU Interfaces  : power={capabilities.get('cpu_power_method')} boost={capabilities.get('has_cpu_boost')} epp={capabilities.get('has_epp_control')}"
    )
    lines.append(
        f"Mini SSD        : {capabilities.get('mini_ssd_classification')} (Slot: {capabilities.get('mini_ssd_pci_address')})"
    )
    lines.append("============================================================")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Super X Helper read-only diagnostic collector")
    parser.add_argument("--json", action="store_true", help="Output raw JSON telemetry to stdout")
    parser.add_argument("-o", "--output", type=str, help="Save an explicitly requested JSON snapshot")
    parser.add_argument(
        "--include-identifiers",
        action="store_true",
        help="Include unique SSD/Bluetooth identifiers. Default public diagnostics redact them.",
    )
    args = parser.parse_args()

    data = collect_all(include_identifiers=args.include_identifiers)
    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        print(f"[✓] Diagnostic snapshot saved to {out_path}")
    print(json.dumps(data, indent=2) if args.json else format_summary(data))
    return 0


if __name__ == "__main__":
    sys.exit(main())
