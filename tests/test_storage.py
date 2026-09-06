from pathlib import Path
import tempfile
import unittest

from superx_helper.collector import get_storage_inventory
from superx_helper.storage import MiniSsdPresenceState, discover_mini_ssd, list_nvme_namespaces


class StorageDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "sys/bus/pci/devices").mkdir(parents=True)
        (self.root / "sys/class/nvme").mkdir(parents=True)
        (self.root / "sys/class/block").mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def _make_mini_pci(self, with_controller=False, with_namespace=False):
        pci = self.root / "sys/bus/pci/devices/0000:c4:00.0"
        pci.mkdir(parents=True)
        (pci / "vendor").write_text("0x1dee\n")
        (pci / "device").write_text("0x2268\n")
        (pci / "current_link_speed").write_text("16.0 GT/s PCIe\n")
        (pci / "current_link_width").write_text("2\n")
        (pci / "max_link_speed").write_text("16.0 GT/s PCIe\n")
        (pci / "max_link_width").write_text("2\n")
        if not with_controller:
            return pci, None
        controller = pci / "nvme/nvme0"
        controller.mkdir(parents=True)
        (controller / "model").write_text("BIWIN Mini SSD 2TB\n")
        (controller / "serial").write_text("SECRET-SERIAL\n")
        (controller / "firmware_rev").write_text("BS14552T\n")
        (controller / "device").symlink_to(Path("../.."))
        (self.root / "sys/class/nvme/nvme0").symlink_to(controller)
        if with_namespace:
            (self.root / "sys/class/block/nvme0n1").mkdir()
        return pci, controller

    def test_absent(self):
        self.assertEqual(discover_mini_ssd(str(self.root)).state, MiniSsdPresenceState.ABSENT)

    def test_pcie_only_without_controller(self):
        self._make_mini_pci()
        found = discover_mini_ssd(str(self.root))
        self.assertEqual(found.state, MiniSsdPresenceState.PCIE_ONLY)
        self.assertEqual(found.pci_address, "0000:c4:00.0")

    def test_pcie_only_without_namespace(self):
        self._make_mini_pci(with_controller=True)
        found = discover_mini_ssd(str(self.root))
        self.assertEqual(found.state, MiniSsdPresenceState.PCIE_ONLY)
        self.assertEqual(found.controller, "nvme0")

    def test_nvme_present_requires_namespace(self):
        _, controller = self._make_mini_pci(with_controller=True, with_namespace=True)
        self.assertEqual(list_nvme_namespaces(controller, "nvme0", str(self.root)), ["nvme0n1"])
        found = discover_mini_ssd(str(self.root))
        self.assertEqual(found.state, MiniSsdPresenceState.NVME_PRESENT)
        self.assertEqual(found.namespaces, ["nvme0n1"])

    def test_storage_inventory_redacts_serial_by_default(self):
        self._make_mini_pci(with_controller=True, with_namespace=True)
        data = get_storage_inventory(sysfs_root=str(self.root))
        self.assertEqual(data["mini_ssd"]["state"], "NVME_PRESENT")
        self.assertEqual(data["mini_ssd"]["reliability"], "NOT_QUALIFIED")
        self.assertEqual(data["controllers"][0]["namespaces"], ["nvme0n1"])
        self.assertEqual(data["controllers"][0]["serial"], "REDACTED")

    def test_storage_inventory_identifier_opt_in(self):
        self._make_mini_pci(with_controller=True, with_namespace=True)
        data = get_storage_inventory(sysfs_root=str(self.root), include_identifiers=True)
        self.assertEqual(data["controllers"][0]["serial"], "SECRET-SERIAL")


if __name__ == "__main__":
    unittest.main()
