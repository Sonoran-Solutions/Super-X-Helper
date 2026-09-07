"""Low-level capability discovery for Super X Helper.

Discovery reports what interfaces exist.  It never grants permission to use a
write interface; write authorization is handled by the service/backend policy.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import os
from pathlib import Path
import subprocess
from typing import Any, Dict, List, Optional

from superx_helper.storage import discover_mini_ssd, rooted


@dataclass
class PlatformCapabilities:
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
    cpu_power_method: str = "none"

    # Display / Backlight controls
    has_backlight_control: bool = False
    backlight_path: Optional[str] = None
    backlight_max: Optional[int] = None

    # Storage diagnostics
    has_mini_ssd: bool = False
    mini_ssd_pci_address: Optional[str] = None
    mini_ssd_controller: Optional[str] = None
    mini_ssd_namespaces: List[str] = field(default_factory=list)
    mini_ssd_classification: str = "ABSENT"

    # Driver & ownership status
    oxpec_driver_loaded: bool = False
    oxpec_driver_available: bool = False
    conflicting_daemons: List[str] = field(default_factory=list)
    ownership_state: str = "UNCONTESTED"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def find_hwmon_by_name(name_query: str, sysfs_hwmon: str = "/sys/class/hwmon") -> Optional[Path]:
    base = Path(sysfs_hwmon)
    if not base.exists():
        return None
    for hw in base.glob("hwmon*"):
        name_file = hw / "name"
        if name_file.is_file():
            try:
                if name_file.read_text(encoding="utf-8").strip() == name_query:
                    return hw
            except OSError:
                pass
    return None


def detect_conflicting_daemons() -> List[str]:
    conflicts: List[str] = []
    known_daemons = ["hhd", "inputplumber", "power-profiles-daemon", "tuned", "tlp"]
    try:
        out = subprocess.run(
            ["pgrep", "-l", "|".join(known_daemons)],
            capture_output=True,
            text=True,
            check=False,
            timeout=2,
        )
        for line in out.stdout.splitlines():
            parts = line.strip().split(None, 1)
            if len(parts) < 2:
                continue
            cmd = parts[1]
            for daemon in known_daemons:
                if daemon in cmd and daemon not in conflicts:
                    conflicts.append(daemon)
    except (OSError, subprocess.SubprocessError):
        pass
    return conflicts


def _module_available(sysfs_root: str) -> bool:
    # A fake sysfs root used by tests should never accidentally inspect the host.
    if sysfs_root:
        fake_module = rooted(sysfs_root, "/lib/modules/oxpec.ko.zst")
        return fake_module.exists()
    try:
        kernel_rel = os.uname().release
        return Path(
            f"/lib/modules/{kernel_rel}/kernel/drivers/platform/x86/oxpec.ko.zst"
        ).exists()
    except OSError:
        return False


def detect_capabilities(
    sysfs_root: str = "",
    sysfs_hwmon: Optional[str] = None,
) -> PlatformCapabilities:
    caps = PlatformCapabilities()

    hwmon_base = sysfs_hwmon or str(rooted(sysfs_root, "/sys/class/hwmon"))
    # The oxpec platform driver registers its hwmon chip as "oxp_ec" (renamed
    # from "oxpec" in upstream commit 36a65fa).  Match the current name first
    # and keep the legacy name as a fallback for older kernels.
    oxp_hwmon = find_hwmon_by_name("oxp_ec", sysfs_hwmon=hwmon_base) or find_hwmon_by_name(
        "oxpec", sysfs_hwmon=hwmon_base
    )
    if oxp_hwmon:
        caps.oxpec_driver_loaded = True
        caps.oxpec_driver_available = True
        try:
            caps.fan_hwmon_name = (oxp_hwmon / "name").read_text(
                encoding="utf-8"
            ).strip()
        except OSError:
            caps.fan_hwmon_name = "oxp_ec"
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
        caps.oxpec_driver_available = _module_available(sysfs_root)

    cpu_base = rooted(sysfs_root, "/sys/devices/system/cpu")
    boost_file = cpu_base / "cpufreq/boost"
    if boost_file.exists():
        caps.has_cpu_boost = True
        caps.cpu_boost_path = str(boost_file)

    epp_file = cpu_base / "cpufreq/policy0/energy_performance_preference"
    epp_available = cpu_base / "cpufreq/policy0/energy_performance_available_preferences"
    if epp_file.exists():
        caps.has_epp_control = True
        caps.epp_path = str(epp_file)
        if epp_available.exists():
            try:
                caps.epp_available_preferences = epp_available.read_text().strip().split()
            except OSError:
                pass

    powercap = rooted(sysfs_root, "/sys/class/powercap")
    if (powercap / "intel-rapl:0").exists():
        caps.cpu_power_method = "rapl"
    elif caps.has_epp_control:
        caps.cpu_power_method = "epp_only"

    backlight_root = rooted(sysfs_root, "/sys/class/backlight")
    if backlight_root.exists():
        for backlight in backlight_root.iterdir():
            brightness = backlight / "brightness"
            max_brightness = backlight / "max_brightness"
            if brightness.exists() and max_brightness.exists():
                caps.has_backlight_control = True
                caps.backlight_path = str(brightness)
                try:
                    caps.backlight_max = int(max_brightness.read_text().strip())
                except (OSError, ValueError):
                    caps.backlight_max = None
                break

    mini = discover_mini_ssd(sysfs_root)
    caps.has_mini_ssd = mini.state.value != "ABSENT"
    caps.mini_ssd_pci_address = mini.pci_address
    caps.mini_ssd_controller = mini.controller
    caps.mini_ssd_namespaces = mini.namespaces
    caps.mini_ssd_classification = mini.state.value

    caps.conflicting_daemons = detect_conflicting_daemons() if not sysfs_root else []
    if not caps.conflicting_daemons:
        caps.ownership_state = "UNCONTESTED"
    elif "hhd" in caps.conflicting_daemons:
        caps.ownership_state = "COEXISTING"
    else:
        caps.ownership_state = "CONFLICT"

    return caps
