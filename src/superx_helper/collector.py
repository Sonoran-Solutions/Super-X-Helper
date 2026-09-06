#!/usr/bin/env python3
"""Super X Helper - Read-Only Diagnostic Collector (SX-003).

Safely inspects the hardware, firmware, platform drivers, and storage
topology of the ONEXPLAYER Super X without writing or modifying hardware state.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Dict, List, Optional


def _read_sysfs_text(path: str | Path) -> Optional[str]:
    """Read a sysfs file safely. Returns stripped text or None on failure."""
    try:
        p = Path(path)
        if p.exists() and p.is_file():
            with open(p, "r", encoding="utf-8", errors="replace") as f:
                return f.read().strip()
    except Exception:
        pass
    return None


def _read_sysfs_int(path: str | Path) -> Optional[int]:
    """Read a sysfs file containing an integer."""
    val = _read_sysfs_text(path)
    if val is not None:
        try:
            return int(val)
        except ValueError:
            pass
    return None


def get_dmi_info(base_path: str = "/sys/class/dmi/id") -> Dict[str, Any]:
    """Collect immutable system DMI identity."""
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
    dmi: Dict[str, Any] = {}
    for f in fields:
        dmi[f] = _read_sysfs_text(os.path.join(base_path, f))
    return dmi


def get_os_kernel_info() -> Dict[str, Any]:
    """Collect kernel version and OS release metadata."""
    os_info: Dict[str, Any] = {
        "kernel_release": None,
        "kernel_version": None,
        "os_name": None,
        "os_version": None,
        "os_id": None,
    }
    try:
        uname = os.uname()
        os_info["kernel_release"] = uname.release
        os_info["kernel_version"] = uname.version
        os_info["architecture"] = uname.machine
    except Exception:
        pass

    os_release_text = _read_sysfs_text("/etc/os-release")
    if os_release_text:
        for line in os_release_text.splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                v = v.strip('"\'')
                if k == "NAME":
                    os_info["os_name"] = v
                elif k == "VERSION":
                    os_info["os_version"] = v
                elif k == "ID":
                    os_info["os_id"] = v
    return os_info


def get_cpu_info() -> Dict[str, Any]:
    """Collect CPU specifications, topology, and scaling configuration."""
    cpu: Dict[str, Any] = {
        "model_name": None,
        "logical_cores": os.cpu_count() or 0,
        "scaling_driver": _read_sysfs_text(
            "/sys/devices/system/cpu/cpufreq/policy0/scaling_driver"
        ),
        "scaling_governor": _read_sysfs_text(
            "/sys/devices/system/cpu/cpufreq/policy0/scaling_governor"
        ),
        "epp": _read_sysfs_text(
            "/sys/devices/system/cpu/cpufreq/policy0/energy_performance_preference"
        ),
        "epp_available": _read_sysfs_text(
            "/sys/devices/system/cpu/cpufreq/policy0/energy_performance_available_preferences"
        ),
        "boost_enabled": _read_sysfs_int(
            "/sys/devices/system/cpu/cpufreq/boost"
        ),
    }

    try:
        cpuinfo = _read_sysfs_text("/proc/cpuinfo")
        if cpuinfo:
            for line in cpuinfo.splitlines():
                if line.startswith("model name"):
                    cpu["model_name"] = line.split(":", 1)[1].strip()
                    break
    except Exception:
        pass

    return cpu


def get_battery_info() -> Dict[str, Any]:
    """Collect battery state from sysfs."""
    bat_path = Path("/sys/class/power_supply/BAT0")
    if not bat_path.exists():
        return {"present": False}

    energy_now = _read_sysfs_int(bat_path / "energy_now")
    energy_full = _read_sysfs_int(bat_path / "energy_full")
    energy_full_design = _read_sysfs_int(bat_path / "energy_full_design")

    return {
        "present": (_read_sysfs_int(bat_path / "present") == 1),
        "status": _read_sysfs_text(bat_path / "status"),
        "capacity_pct": _read_sysfs_int(bat_path / "capacity"),
        "manufacturer": _read_sysfs_text(bat_path / "manufacturer"),
        "model_name": _read_sysfs_text(bat_path / "model_name"),
        "energy_now_wh": round(energy_now / 1e6, 2) if energy_now else None,
        "energy_full_wh": round(energy_full / 1e6, 2) if energy_full else None,
        "energy_design_wh": round(energy_full_design / 1e6, 2)
        if energy_full_design
        else None,
        "voltage_now_v": round(
            (_read_sysfs_int(bat_path / "voltage_now") or 0) / 1e6, 2
        )
        if _read_sysfs_int(bat_path / "voltage_now")
        else None,
    }


def get_hwmon_info(
    sysfs_hwmon: str = "/sys/class/hwmon",
) -> List[Dict[str, Any]]:
    """Enumerate all hwmon sensors and current readings."""
    sensors: List[Dict[str, Any]] = []
    base = Path(sysfs_hwmon)
    if not base.exists():
        return sensors

    for hw in sorted(base.glob("hwmon*")):
        name = _read_sysfs_text(hw / "name") or hw.name
        readings: Dict[str, Any] = {}

        # Collect temperatures
        for t_inp in sorted(hw.glob("temp*_input")):
            prefix = t_inp.name.replace("_input", "")
            raw_temp = _read_sysfs_int(t_inp)
            temp_c = round(raw_temp / 1000.0, 1) if raw_temp is not None else None
            label = _read_sysfs_text(hw / f"{prefix}_label") or prefix
            readings[label] = {"temp_c": temp_c}

        # Collect fans / PWM
        for fan_inp in sorted(hw.glob("fan*_input")):
            prefix = fan_inp.name.replace("_input", "")
            rpm = _read_sysfs_int(fan_inp)
            label = _read_sysfs_text(hw / f"{prefix}_label") or prefix
            readings[label] = {"rpm": rpm}

        for pwm in sorted(hw.glob("pwm*")):
            if pwm.is_file() and not pwm.name.endswith("_enable"):
                val = _read_sysfs_int(pwm)
                enable_val = _read_sysfs_int(hw / f"{pwm.name}_enable")
                readings[pwm.name] = {
                    "duty": val,
                    "enable_mode": enable_val,
                }

        # Collect power
        for pwr_inp in sorted(hw.glob("power*_input")):
            prefix = pwr_inp.name.replace("_input", "")
            u_watt = _read_sysfs_int(pwr_inp)
            watt = round(u_watt / 1e6, 2) if u_watt is not None else None
            label = _read_sysfs_text(hw / f"{prefix}_label") or prefix
            readings[label] = {"watts": watt}

        sensors.append(
            {
                "id": hw.name,
                "name": name,
                "readings": readings,
            }
        )

    return sensors


def get_display_info() -> Dict[str, Any]:
    """Collect internal panel DRM modes and backlight brightness."""
    drm_path = Path("/sys/class/drm")
    display: Dict[str, Any] = {
        "connectors": [],
        "backlight": {},
    }

    if drm_path.exists():
        for card_conn in sorted(drm_path.glob("card*-*")):
            status = _read_sysfs_text(card_conn / "status")
            if status == "connected":
                modes_raw = _read_sysfs_text(card_conn / "modes") or ""
                modes = [m.strip() for m in modes_raw.splitlines() if m.strip()]
                display["connectors"].append(
                    {
                        "connector": card_conn.name,
                        "status": status,
                        "modes": modes[:5],  # top 5 modes
                        "primary_mode": modes[0] if modes else None,
                    }
                )

    bl_path = Path("/sys/class/backlight")
    if bl_path.exists():
        for bl in bl_path.iterdir():
            actual = _read_sysfs_int(bl / "actual_brightness")
            max_b = _read_sysfs_int(bl / "max_brightness")
            pct = round((actual / max_b) * 100, 1) if (actual and max_b) else None
            display["backlight"][bl.name] = {
                "actual": actual,
                "max": max_b,
                "percent": pct,
            }

    return display


def get_storage_inventory() -> Dict[str, Any]:
    """Inspect NVMe controllers and classify PCIe link states."""
    nvme_devices: List[Dict[str, Any]] = []
    nvme_class = Path("/sys/class/nvme")

    if nvme_class.exists():
        for ctrl in sorted(nvme_class.glob("nvme*")):
            model = _read_sysfs_text(ctrl / "model")
            serial = _read_sysfs_text(ctrl / "serial")
            firmware = _read_sysfs_text(ctrl / "firmware_rev")

            # Resolve underlying PCI device
            pci_link_speed = None
            pci_link_width = None
            max_link_speed = None
            max_link_width = None
            pci_address = None
            vendor_device = None

            device_symlink = ctrl / "device"
            if device_symlink.exists():
                try:
                    resolved_pci = device_symlink.resolve()
                    pci_address = resolved_pci.name
                    pci_link_speed = _read_sysfs_text(
                        resolved_pci / "current_link_speed"
                    )
                    pci_link_width = _read_sysfs_int(
                        resolved_pci / "current_link_width"
                    )
                    max_link_speed = _read_sysfs_text(
                        resolved_pci / "max_link_speed"
                    )
                    max_link_width = _read_sysfs_int(
                        resolved_pci / "max_link_width"
                    )
                    v_id = _read_sysfs_text(resolved_pci / "vendor")
                    d_id = _read_sysfs_text(resolved_pci / "device")
                    if v_id and d_id:
                        vendor_device = (
                            f"{v_id.replace('0x', '')}:{d_id.replace('0x', '')}"
                        )
                except Exception:
                    pass

            # Classify storage state per docs/MINI_SSD.md
            is_mini_ssd = "BIWIN" in (model or "").upper() or "2268" in (
                vendor_device or ""
            )
            classification = "NVME_PRESENT"

            # Check namespaces/block devices
            namespaces = [
                ns.name for ns in ctrl.parent.glob(f"{ctrl.name}n*") if ns.is_dir()
            ]

            nvme_devices.append(
                {
                    "controller": ctrl.name,
                    "model": model,
                    "serial": serial,
                    "firmware_rev": firmware,
                    "is_removable_mini_ssd": is_mini_ssd,
                    "classification": classification,
                    "pci": {
                        "address": pci_address,
                        "vendor_device": vendor_device,
                        "link_speed": pci_link_speed,
                        "link_width": pci_link_width,
                        "max_link_speed": max_link_speed,
                        "max_link_width": max_link_width,
                    },
                    "namespaces": namespaces,
                }
            )

    return {
        "controllers": nvme_devices,
        "count": len(nvme_devices),
    }


def get_connectivity_inventory() -> Dict[str, Any]:
    """Inspect Bluetooth adapter and known platform USB controllers."""
    bt_adapters = []
    bt_path = Path("/sys/class/bluetooth")
    if bt_path.exists():
        for hci in sorted(bt_path.glob("hci*")):
            addr = _read_sysfs_text(hci / "address")
            bt_adapters.append(
                {
                    "name": hci.name,
                    "address": addr if addr else "present",
                }
            )

    # Check known USB devices
    usb_devices = []
    usb_base = Path("/sys/bus/usb/devices")
    if usb_base.exists():
        for dev in sorted(usb_base.glob("*")):
            v_id = _read_sysfs_text(dev / "idVendor")
            p_id = _read_sysfs_text(dev / "idProduct")
            mfg = _read_sysfs_text(dev / "manufacturer")
            prod = _read_sysfs_text(dev / "product")
            if v_id and p_id:
                usb_devices.append(
                    {
                        "dev": dev.name,
                        "vid_pid": f"{v_id}:{p_id}",
                        "manufacturer": mfg,
                        "product": prod,
                    }
                )

    return {
        "bluetooth_adapters": bt_adapters,
        "usb_device_count": len(usb_devices),
        "known_platform_peripherals": [
            d
            for d in usb_devices
            if d["vid_pid"] in ("1a2c:b001", "0e8d:0717", "2808:5952")
        ],
    }


def get_platform_module_status() -> Dict[str, Any]:
    """Inspect loaded platform modules and oxpec presence."""
    modules_loaded: List[str] = []
    try:
        proc_modules = _read_sysfs_text("/proc/modules")
        if proc_modules:
            for line in proc_modules.splitlines():
                mod_name = line.split()[0]
                modules_loaded.append(mod_name)
    except Exception:
        pass

    kernel_rel = os.uname().release
    oxpec_mod_path = Path(
        f"/lib/modules/{kernel_rel}/kernel/drivers/platform/x86/oxpec.ko.zst"
    )
    oxpec_available = oxpec_mod_path.exists()
    oxpec_loaded = "oxpec" in modules_loaded

    return {
        "oxpec_loaded": oxpec_loaded,
        "oxpec_module_available": oxpec_available,
        "oxpec_module_path": str(oxpec_mod_path) if oxpec_available else None,
        "amdgpu_loaded": "amdgpu" in modules_loaded,
        "btusb_loaded": "btusb" in modules_loaded,
    }


def collect_all() -> Dict[str, Any]:
    """Perform a complete read-only collection of system properties."""
    from superx_helper.capabilities import detect_capabilities

    timestamp = (
        datetime.datetime.now(datetime.timezone.utc).isoformat()
    )
    return {
        "timestamp_utc": timestamp,
        "dmi": get_dmi_info(),
        "os_kernel": get_os_kernel_info(),
        "cpu": get_cpu_info(),
        "battery": get_battery_info(),
        "display": get_display_info(),
        "storage": get_storage_inventory(),
        "thermal_sensors": get_hwmon_info(),
        "connectivity": get_connectivity_inventory(),
        "platform_modules": get_platform_module_status(),
        "capabilities": detect_capabilities().to_dict(),
    }


def format_summary(data: Dict[str, Any]) -> str:
    """Format the captured telemetry into a concise human-readable markdown report."""
    dmi = data.get("dmi", {})
    cpu = data.get("cpu", {})
    os_info = data.get("os_kernel", {})
    storage = data.get("storage", {})
    bat = data.get("battery", {})
    disp = data.get("display", {})
    mods = data.get("platform_modules", {})

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
        f"oxpec Driver    : {'LOADED' if mods.get('oxpec_loaded') else 'AVAILABLE (Not Loaded)'} "
        f"[Module: {mods.get('oxpec_module_available')}]",
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
        lines.append(
            f"{tag} {ctrl.get('model')} ({ctrl.get('controller')}, FW: {ctrl.get('firmware_rev')})"
        )
        lines.append(
            f"   PCI Slot: {pci.get('address')} ({pci.get('vendor_device')}) | "
            f"Link: {pci.get('link_speed')} x{pci.get('link_width')} (Max: {pci.get('max_link_speed')} x{pci.get('max_link_width')})"
        )
        lines.append(
            f"   State Classification: {ctrl.get('classification')} | Block Devices: {', '.join(ctrl.get('namespaces', []))}"
        )

    lines.append("")
    lines.append("--- [5. Thermals & Power] ---")
    hw_sensors = data.get("thermal_sensors", [])
    for s in hw_sensors:
        readings = s.get("readings", {})
        temp_strs = [
            f"{k}: {v.get('temp_c')}°C"
            for k, v in readings.items()
            if "temp_c" in v and v.get("temp_c") is not None
        ]
        pwr_strs = [
            f"{k}: {v.get('watts')}W"
            for k, v in readings.items()
            if "watts" in v and v.get("watts") is not None
        ]
        if temp_strs or pwr_strs:
            combined = ", ".join(temp_strs + pwr_strs)
            lines.append(f"  {s.get('name')} ({s.get('id')}): {combined}")

    lines.append(
        f"Battery Status  : {bat.get('status')} ({bat.get('capacity_pct')}%) | "
        f"Capacity: {bat.get('energy_now_wh')} Wh / {bat.get('energy_full_wh')} Wh (Design: {bat.get('energy_design_wh')} Wh)"
    )

    lines.append("")
    lines.append("--- [6. Display & Peripherals] ---")
    for conn in disp.get("connectors", []):
        lines.append(
            f"Display Output  : {conn.get('connector')} [{conn.get('status')}] - Mode: {conn.get('primary_mode')}"
        )
    for bl_name, bl_info in disp.get("backlight", {}).items():
        lines.append(
            f"Backlight       : {bl_name} at {bl_info.get('percent')}% (raw: {bl_info.get('actual')}/{bl_info.get('max')})"
        )

    conn = data.get("connectivity", {})
    lines.append(
        f"Bluetooth       : {len(conn.get('bluetooth_adapters', []))} adapter(s) found"
    )
    lines.append("")
    lines.append("--- [7. Upstream Controls & Ownership] ---")
    caps = data.get("capabilities", {})
    lines.append(f"Ownership State : {caps.get('ownership_state')}")
    fan_status = (
        f"Active ({caps.get('fan_hwmon_name')})"
        if caps.get("has_fan_control")
        else ("Available in tree (not loaded)" if caps.get("oxpec_driver_available") else "Missing")
    )
    lines.append(f"Fan Control     : {fan_status}")
    lines.append(
        f"CPU Power/Boost : Method: {caps.get('cpu_power_method')} | Boost: {'Available' if caps.get('has_cpu_boost') else 'No'} | EPP: {'Available' if caps.get('has_epp_control') else 'No'}"
    )
    lines.append(f"Backlight       : {'Available' if caps.get('has_backlight_control') else 'No'}")
    lines.append(
        f"Mini SSD State  : {caps.get('mini_ssd_classification')} (Slot: {caps.get('mini_ssd_pci_address')})"
    )
    conflicts = caps.get("conflicting_daemons", [])
    lines.append(f"Daemon Contention: {', '.join(conflicts) if conflicts else 'None detected'}")

    lines.append("============================================================")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Super X Helper - Read-Only Diagnostic Collector (SX-003)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON telemetry to stdout",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Print formatted summary report (default)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        help="Save output JSON snapshot to specified file path",
    )

    args = parser.parse_args()

    data = collect_all()

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        print(f"[✓] Diagnostic snapshot saved to {out_path}")

    if args.json:
        print(json.dumps(data, indent=2))
    else:
        print(format_summary(data))

    return 0


if __name__ == "__main__":
    sys.exit(main())
