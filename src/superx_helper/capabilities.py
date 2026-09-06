"""Capability discovery and ownership model for Super X Helper.

Defines the capabilities available on the system, resolves interfaces dynamically,
and detects any conflicting daemons or drivers.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import os
from pathlib import Path
import subprocess
from typing import Any, Dict, List, Optional


@dataclass
class PlatformCapabilities:
    """Discovered platform capabilities and active interface mappings."""

    # Fan controls
    has_fan_control: bool = False
    has_fan_telemetry: bool = False
    fan_hwmon_name: Optional[str] = None
    fan_hwmon_path: Optional[str] = None
    fan_pwm_path: Optional[str] = None
    fan_pwm_enable_path: Optional[str] = None

    # CPU / Power controls
    has_cpu_boost: bool = False
    cpu_boost_path: Optional[str] = None
    has_epp_control: bool = False
    epp_path: Optional[str] = None
    epp_available_preferences: List[str] = field(default_factory=list)
    cpu_power_method: str = "none"  # "rapl", "ryzenadj", "epp_only", "none"

    # Display / Backlight controls
    has_backlight_control: bool = False
    backlight_path: Optional[str] = None
    backlight_max: Optional[int] = None

    # Storage diagnostics
    has_mini_ssd: bool = False
    mini_ssd_pci_address: Optional[str] = None
    mini_ssd_classification: str = "ABSENT"

    # Driver & Ownership Status
    oxpec_driver_loaded: bool = False
    oxpec_driver_available: bool = False
    conflicting_daemons: List[str] = field(default_factory=list)
    ownership_state: str = "UNCONTESTED"  # "UNCONTESTED", "COEXISTING", "CONFLICT"

    def to_dict(self) -> Dict[str, Any]:
        """Convert capabilities to a standard dictionary."""
        return asdict(self)


def find_hwmon_by_name(name_query: str, sysfs_hwmon: str = "/sys/class/hwmon") -> Optional[Path]:
    """Find the hwmon directory whose 'name' attribute matches name_query."""
    base = Path(sysfs_hwmon)
    if not base.exists():
        return None
    for hw in base.glob("hwmon*"):
        name_file = hw / "name"
        if name_file.is_file():
            try:
                content = name_file.read_text(encoding="utf-8").strip()
                if content == name_query:
                    return hw
            except Exception:
                pass
    return None


def detect_conflicting_daemons() -> List[str]:
    """Check for daemons that could contend for fan curves or power limits."""
    conflicts = []
    known_daemons = ["hhd", "inputplumber", "power-profiles-daemon", "tuned", "tlp"]

    # Check via pgrep or ps
    try:
        out = subprocess.run(
            ["pgrep", "-l", "|".join(known_daemons)],
            capture_output=True,
            text=True,
            check=False,
        )
        if out.stdout:
            for line in out.stdout.splitlines():
                parts = line.strip().split(None, 1)
                if len(parts) > 1:
                    cmd = parts[1]
                    for kd in known_daemons:
                        if kd in cmd and kd not in conflicts:
                            conflicts.append(kd)
    except Exception:
        pass

    return conflicts


def detect_capabilities(
    sysfs_root: str = "",
    sysfs_hwmon: Optional[str] = None,
) -> PlatformCapabilities:
    """Detect all system platform capabilities dynamically without hardcoding hwmon numbers."""
    caps = PlatformCapabilities()

    # 1. Inspect oxpec platform driver
    hwmon_base = sysfs_hwmon or (os.path.join(sysfs_root, "sys/class/hwmon") if sysfs_root else "/sys/class/hwmon")
    oxp_hwmon = find_hwmon_by_name("oxpec", sysfs_hwmon=hwmon_base)
    if oxp_hwmon:
        caps.oxpec_driver_loaded = True
        caps.fan_hwmon_name = "oxpec"
        caps.fan_hwmon_path = str(oxp_hwmon)
        pwm1 = oxp_hwmon / "pwm1"
        pwm1_enable = oxp_hwmon / "pwm1_enable"
        if pwm1.exists():
            caps.fan_pwm_path = str(pwm1)
            caps.has_fan_control = True
            caps.has_fan_telemetry = True
        if pwm1_enable.exists():
            caps.fan_pwm_enable_path = str(pwm1_enable)
    else:
        # Check if oxpec module exists on disk
        try:
            kernel_rel = os.uname().release
            mod_path = Path(
                f"/lib/modules/{kernel_rel}/kernel/drivers/platform/x86/oxpec.ko.zst"
            )
            caps.oxpec_driver_available = mod_path.exists()
        except Exception:
            pass

    # 2. Inspect CPU boost and frequency scaling
    cpu_base = Path(os.path.join(sysfs_root, "sys/devices/system/cpu") if sysfs_root else "/sys/devices/system/cpu")
    boost_file = cpu_base / "cpufreq/boost"
    if boost_file.exists():
        caps.has_cpu_boost = True
        caps.cpu_boost_path = str(boost_file)

    epp_file = cpu_base / "cpufreq/policy0/energy_performance_preference"
    epp_avail_file = cpu_base / "cpufreq/policy0/energy_performance_available_preferences"
    if epp_file.exists():
        caps.has_epp_control = True
        caps.epp_path = str(epp_file)
        if epp_avail_file.exists():
            try:
                avail_str = epp_avail_file.read_text(encoding="utf-8").strip()
                caps.epp_available_preferences = avail_str.split()
            except Exception:
                pass

    # Inspect power control method (RAPL / RyzenAdj / EPP)
    powercap_base = Path(os.path.join(sysfs_root, "sys/class/powercap") if sysfs_root else "/sys/class/powercap")
    if (powercap_base / "intel-rapl:0").exists():
        caps.cpu_power_method = "rapl"
    elif caps.has_epp_control:
        caps.cpu_power_method = "epp_only"

    # 3. Inspect Backlight
    bl_base = Path(os.path.join(sysfs_root, "sys/class/backlight") if sysfs_root else "/sys/class/backlight")
    if bl_base.exists():
        for bl in bl_base.iterdir():
            brightness_file = bl / "brightness"
            max_b_file = bl / "max_brightness"
            if brightness_file.exists() and max_b_file.exists():
                caps.has_backlight_control = True
                caps.backlight_path = str(brightness_file)
                try:
                    caps.backlight_max = int(max_b_file.read_text(encoding="utf-8").strip())
                except Exception:
                    pass
                break

    # 4. Inspect Mini SSD status
    pci_base = Path(os.path.join(sysfs_root, "sys/bus/pci/devices") if sysfs_root else "/sys/bus/pci/devices")
    if pci_base.exists():
        for pci_dev in pci_base.iterdir():
            v_id_file = pci_dev / "vendor"
            d_id_file = pci_dev / "device"
            if v_id_file.exists() and d_id_file.exists():
                try:
                    v_id = v_id_file.read_text(encoding="utf-8").strip()
                    d_id = d_id_file.read_text(encoding="utf-8").strip()
                    # BIWIN Storage Technology 1dee:2268
                    if "1dee" in v_id and "2268" in d_id:
                        caps.has_mini_ssd = True
                        caps.mini_ssd_pci_address = pci_dev.name
                        nvme_dir = pci_dev / "nvme"
                        if nvme_dir.exists():
                            caps.mini_ssd_classification = "NVME_PRESENT"
                        else:
                            caps.mini_ssd_classification = "PCIE_ONLY"
                        break
                except Exception:
                    pass

    # 5. Inspect Conflicting Daemons & Ownership
    caps.conflicting_daemons = detect_conflicting_daemons()
    if not caps.conflicting_daemons:
        caps.ownership_state = "UNCONTESTED"
    elif "hhd" in caps.conflicting_daemons:
        caps.ownership_state = "COEXISTING"
    else:
        caps.ownership_state = "CONFLICT"

    return caps
