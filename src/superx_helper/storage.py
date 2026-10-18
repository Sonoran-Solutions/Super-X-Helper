"""Read-only storage discovery helpers.

Presence classification deliberately stops at transport visibility.  A drive is
never labelled HEALTHY merely because PCIe/NVMe enumeration currently succeeds.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
import re
from typing import Dict, List, Optional

MINI_SSD_VENDOR_ID = "1dee"
MINI_SSD_DEVICE_ID = "2268"
_NAMESPACE_RE = re.compile(r"^nvme\d+n\d+$")
_CONTROLLER_RE = re.compile(r"^nvme\d+$")


class MiniSsdPresenceState(str, Enum):
    ABSENT = "ABSENT"
    PCIE_ONLY = "PCIE_ONLY"
    NVME_PRESENT = "NVME_PRESENT"


@dataclass(frozen=True)
class MiniSsdPresence:
    state: MiniSsdPresenceState
    pci_address: Optional[str] = None
    controller: Optional[str] = None
    namespaces: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        data = asdict(self)
        data["state"] = self.state.value
        return data


def rooted(sysfs_root: str, absolute_path: str) -> Path:
    path = absolute_path.lstrip("/")
    return Path(sysfs_root) / path if sysfs_root else Path("/") / path


def read_mini_ssd_telemetry(
    pci_address: Optional[str], sysfs_root: str = ""
) -> Dict[str, object]:
    """Read cheap PCIe and controller-matched hwmon telemetry; never infer health."""
    data = {
        "link_speed": None,
        "link_width": None,
        "max_link_speed": None,
        "max_link_width": None,
        "aspm": {"l1": None, "l1_1": None, "l1_2": None},
        "temperature_c": None,
    }
    if pci_address is None:
        return data

    def read_text(path: Path) -> Optional[str]:
        try:
            return path.read_text().strip() or None
        except (OSError, UnicodeError):
            return None

    def read_int(path: Path) -> Optional[int]:
        try:
            return int(read_text(path))
        except (TypeError, ValueError):
            return None

    pci = rooted(sysfs_root, "/sys/bus/pci/devices") / pci_address
    data["link_speed"] = read_text(pci / "current_link_speed")
    data["link_width"] = read_int(pci / "current_link_width")
    data["max_link_speed"] = read_text(pci / "max_link_speed")
    data["max_link_width"] = read_int(pci / "max_link_width")
    data["aspm"] = {
        name: {"0": False, "1": True}.get(read_text(pci / "link" / f"{name}_aspm"))
        for name in ("l1", "l1_1", "l1_2")
    }
    try:
        resolved_pci = pci.resolve(strict=True)
        for hwmon in rooted(sysfs_root, "/sys/class/hwmon").iterdir():
            if read_text(hwmon / "name") != "nvme":
                continue
            try:
                device = (hwmon / "device").resolve(strict=True)
            except (OSError, RuntimeError):
                continue
            if device.is_relative_to(resolved_pci):
                temperature = read_int(hwmon / "temp1_input")
                if temperature is not None:
                    data["temperature_c"] = round(temperature / 1000.0, 1)
                    break
    except (OSError, RuntimeError):
        pass
    return data


def read_mini_ssd_power_state(
    pci_address: Optional[str], sysfs_root: str = ""
) -> Dict[str, object]:
    """Read PCIe power-management flags without changing device state."""
    data: Dict[str, object] = dict.fromkeys(
        ("l1_1_pcipm", "l1_2_pcipm", "clkpm", "d3cold_allowed", "runtime_status")
    )
    if pci_address is None:
        return data

    pci = rooted(sysfs_root, "/sys/bus/pci/devices") / pci_address
    for name, path in (
        ("l1_1_pcipm", "link/l1_1_pcipm"),
        ("l1_2_pcipm", "link/l1_2_pcipm"),
        ("clkpm", "link/clkpm"),
        ("d3cold_allowed", "d3cold_allowed"),
        ("runtime_status", "power/runtime_status"),
    ):
        try:
            value = (pci / path).read_text().strip()
        except (OSError, UnicodeError):
            continue
        data[name] = (value or None) if name == "runtime_status" else {"0": False, "1": True}.get(value)
    return data


def read_namespace_io(
    namespace: Optional[str], sysfs_root: str = ""
) -> Optional[Dict[str, object]]:
    """Read cumulative block I/O counters and mount presence, excluding mount details."""
    if namespace is None:
        return None

    data: Dict[str, object] = {"namespace": namespace}
    try:
        fields = rooted(sysfs_root, f"/sys/block/{namespace}/stat").read_text().split()
    except (OSError, UnicodeError):
        fields = []
    for name, index in (("reads_completed", 0), ("sectors_read", 2),
                        ("writes_completed", 4), ("sectors_written", 6)):
        try:
            data[name] = int(fields[index])
        except (IndexError, ValueError):
            data[name] = None

    source_pattern = re.compile(rf"/dev/{re.escape(namespace)}(?:p[0-9]+)?")
    data["mounted"] = None
    try:
        with rooted(sysfs_root, "/proc/self/mountinfo").open() as mountinfo:
            data["mounted"] = False
            for line in mountinfo:
                fields = line.partition(" - ")[2].split()
                if len(fields) > 1 and source_pattern.fullmatch(fields[1]):
                    data["mounted"] = True
                    break
    except (OSError, UnicodeError):
        data["mounted"] = None
    return data


def normalize_pci_id(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    return value.strip().lower().removeprefix("0x")


def list_nvme_namespaces(
    controller_path: Path,
    controller_name: str,
    sysfs_root: str = "",
) -> List[str]:
    """Return namespace block-device names for an NVMe controller.

    Linux commonly exposes namespaces below the controller's resolved sysfs
    directory and also under ``/sys/class/block``.  Looking only beside
    ``/sys/class/nvme/nvmeX`` misses real namespaces on some kernels.
    """

    found = set()

    try:
        for candidate in controller_path.glob(f"{controller_name}n*"):
            if _NAMESPACE_RE.match(candidate.name):
                found.add(candidate.name)
    except OSError:
        pass

    block_root = rooted(sysfs_root, "/sys/class/block")
    if block_root.exists():
        try:
            for candidate in block_root.glob(f"{controller_name}n*"):
                if _NAMESPACE_RE.match(candidate.name):
                    found.add(candidate.name)
        except OSError:
            pass

    return sorted(found)


def discover_mini_ssd(sysfs_root: str = "") -> MiniSsdPresence:
    """Classify the known BIWIN Mini SSD from PCIe through namespace presence."""

    pci_root = rooted(sysfs_root, "/sys/bus/pci/devices")
    if not pci_root.exists():
        return MiniSsdPresence(MiniSsdPresenceState.ABSENT)

    for pci_dev in sorted(pci_root.iterdir()):
        try:
            vendor = normalize_pci_id((pci_dev / "vendor").read_text().strip())
            device = normalize_pci_id((pci_dev / "device").read_text().strip())
        except (FileNotFoundError, OSError):
            continue

        if vendor != MINI_SSD_VENDOR_ID or device != MINI_SSD_DEVICE_ID:
            continue

        nvme_root = pci_dev / "nvme"
        if not nvme_root.exists():
            return MiniSsdPresence(
                MiniSsdPresenceState.PCIE_ONLY,
                pci_address=pci_dev.name,
            )

        controllers = [
            path for path in sorted(nvme_root.iterdir()) if _CONTROLLER_RE.match(path.name)
        ]
        if not controllers:
            return MiniSsdPresence(
                MiniSsdPresenceState.PCIE_ONLY,
                pci_address=pci_dev.name,
            )

        for controller in controllers:
            namespaces = list_nvme_namespaces(controller, controller.name, sysfs_root)
            if namespaces:
                return MiniSsdPresence(
                    MiniSsdPresenceState.NVME_PRESENT,
                    pci_address=pci_dev.name,
                    controller=controller.name,
                    namespaces=namespaces,
                )

        return MiniSsdPresence(
            MiniSsdPresenceState.PCIE_ONLY,
            pci_address=pci_dev.name,
            controller=controllers[0].name,
        )

    return MiniSsdPresence(MiniSsdPresenceState.ABSENT)
