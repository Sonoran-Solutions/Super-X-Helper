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
