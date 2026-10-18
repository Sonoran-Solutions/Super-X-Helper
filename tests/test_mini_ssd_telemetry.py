from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

from superx_helper.contracts import CapabilityId, CapabilityRecord, CapabilityStatus, SafetyState
from superx_helper.platform import PlatformBackend
from superx_helper.service import SuperXService
from superx_helper.storage import read_mini_ssd_telemetry
from superx_helper.ui.widgets import (
    MiniSsdStatusCard,
    format_mini_ssd_telemetry,
    format_observed_value,
)


EMPTY_TELEMETRY = {
    "link_speed": None,
    "link_width": None,
    "max_link_speed": None,
    "max_link_width": None,
    "aspm": {"l1": None, "l1_1": None, "l1_2": None},
    "temperature_c": None,
}


class MiniSsdTelemetryTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.address = "0000:c4:00.0"
        bus = self.root / "sys/bus/pci/devices"
        bus.mkdir(parents=True)
        for address, controller, hwmon, temperature, vendor, device in (
            ("0000:c3:00.0", "nvme1", "hwmon3", "44850", "0x1e0f", "0x0033"),
            (self.address, "nvme0", "hwmon4", "46850", "0x1dee", "0x2268"),
        ):
            pci = self.root / "sys/devices/pci0000:00/0000:00:03.1" / address
            nvme = pci / "nvme" / controller
            (nvme / f"{controller}n1").mkdir(parents=True)
            (pci / "vendor").write_text(vendor)
            (pci / "device").write_text(device)
            (bus / address).symlink_to(pci, target_is_directory=True)
            sensor = self.root / "sys/class/hwmon" / hwmon
            sensor.mkdir(parents=True)
            (sensor / "name").write_text("nvme\n")
            (sensor / "device").symlink_to(nvme, target_is_directory=True)
            (sensor / "temp1_input").write_text(temperature)
            (sensor / "temp1_label").write_text("Composite\n")
        self.pci = (bus / self.address).resolve()
        for name, value in (
            ("current_link_speed", "16.0 GT/s PCIe"),
            ("current_link_width", "2"),
            ("max_link_speed", "16.0 GT/s PCIe"),
            ("max_link_width", "2"),
        ):
            (self.pci / name).write_text(value + "\n")
        (self.pci / "link").mkdir()
        for name in ("l1_aspm", "l1_1_aspm", "l1_2_aspm"):
            (self.pci / "link" / name).write_text("1\n")

    def telemetry(self):
        return read_mini_ssd_telemetry(self.address, str(self.root))

    def snapshot(self):
        with patch("superx_helper.service.get_battery_info", return_value={}), patch(
            "superx_helper.service.get_display_info", return_value={}
        ):
            return SuperXService(platform=PlatformBackend(sysfs_root=str(self.root))).get_capability_snapshot()

    def test_telemetry_matches_mini_pci_not_internal_ssd(self):
        self.assertEqual(self.telemetry(), {
            "link_speed": "16.0 GT/s PCIe",
            "link_width": 2,
            "max_link_speed": "16.0 GT/s PCIe",
            "max_link_width": 2,
            "aspm": {"l1": True, "l1_1": True, "l1_2": True},
            "temperature_c": 46.9,
        })

    def test_missing_optional_files(self):
        shutil.rmtree(self.pci / "link")
        shutil.rmtree(self.root / "sys/class/hwmon")
        telemetry = self.telemetry()
        self.assertEqual(telemetry["aspm"], EMPTY_TELEMETRY["aspm"])
        self.assertIsNone(telemetry["temperature_c"])
        self.assertEqual(telemetry["link_width"], 2)
        for name in ("current_link_speed", "current_link_width", "max_link_speed", "max_link_width"):
            (self.pci / name).unlink()
        self.assertEqual(self.telemetry(), EMPTY_TELEMETRY)

    def test_absent_pci(self):
        self.assertEqual(read_mini_ssd_telemetry(None, str(self.root)), EMPTY_TELEMETRY)
        self.assertEqual(read_mini_ssd_telemetry("0000:ff:00.0", str(self.root)), EMPTY_TELEMETRY)

    def test_unreadable_files(self):
        with patch.object(Path, "read_text", side_effect=PermissionError):
            self.assertEqual(self.telemetry(), EMPTY_TELEMETRY)

    def test_invalid_numeric_fields_and_disabled_aspm(self):
        (self.pci / "current_link_width").write_text("unknown")
        (self.pci / "link/l1_aspm").write_text("0")
        (self.pci / "link/l1_1_aspm").write_text("invalid")
        (self.root / "sys/class/hwmon/hwmon4/temp1_input").write_text("invalid")
        telemetry = self.telemetry()
        self.assertIsNone(telemetry["link_width"])
        self.assertEqual(telemetry["aspm"], {"l1": False, "l1_1": None, "l1_2": True})
        self.assertIsNone(telemetry["temperature_c"])

    def test_hwmon_requires_resolved_directory_ancestry(self):
        device = self.root / "sys/class/hwmon/hwmon4/device"
        device.unlink()
        sibling = self.pci.with_name(self.address + "-other") / "nvme/nvme0"
        sibling.mkdir(parents=True)
        device.symlink_to(sibling, target_is_directory=True)
        self.assertIsNone(self.telemetry()["temperature_c"])
        device.unlink()
        device.symlink_to("missing-controller")
        self.assertIsNone(self.telemetry()["temperature_c"])

    def test_service_snapshot_keeps_reliability_unchanged(self):
        snapshot = self.snapshot()
        presence = snapshot.by_id(CapabilityId.MINI_SSD_PRESENCE.value)
        self.assertEqual(presence.observed_value, {
            "state": "NVME_PRESENT",
            "pci_address": self.address,
            "controller": "nvme0",
            "namespaces": ["nvme0n1"],
            "reliability": "NOT_QUALIFIED",
            **self.telemetry(),
        })
        self.assertFalse(presence.can_write)
        self.assertEqual(snapshot.by_id(CapabilityId.MINI_SSD_RELIABILITY.value), CapabilityRecord(
            CapabilityId.MINI_SSD_RELIABILITY.value,
            "Mini SSD Reliability",
            CapabilityStatus.READ_ONLY,
            read_supported=True,
            write_supported=False,
            locally_validated=True,
            observed_value="NOT_QUALIFIED",
            owner="Super X Helper research",
            backend="storage",
            warnings=["Do not use the Mini SSD as the only copy of important data until reliability qualification passes."],
            safety_state=SafetyState.NOT_QUALIFIED,
        ))

    def test_formatter_and_observed_presence(self):
        self.assertEqual(format_mini_ssd_telemetry(self.telemetry()), "Gen4 x2 · 46.9 °C")
        presence = self.snapshot().by_id(CapabilityId.MINI_SSD_PRESENCE.value)
        self.assertIn("Gen4 x2 · 46.9 °C", format_observed_value(presence))

    def test_formatter_downtrained_speed_or_width(self):
        for speed, width in (("8.0 GT/s PCIe", 1), ("8.0 GT/s PCIe", 2), ("16.0 GT/s PCIe", 1)):
            with self.subTest(speed=speed, width=width):
                telemetry = {**self.telemetry(), "link_speed": speed, "link_width": width}
                self.assertIn("(max Gen4 x2)", format_mini_ssd_telemetry(telemetry))

    def test_formatter_partial_empty_and_unknown_speed(self):
        cases = (
            ({"temperature_c": 46.9}, "46.9 °C"),
            ({"link_speed": "16.0 GT/s PCIe", "link_width": 2}, "Gen4 x2"),
            ({"link_width": 2}, "x2"),
            ({"link_speed": "128.0 GT/s PCIe"}, "128.0 GT/s PCIe"),
            ({}, None),
            (EMPTY_TELEMETRY, None),
            (None, None),
        )
        for telemetry, expected in cases:
            with self.subTest(telemetry=telemetry):
                self.assertEqual(format_mini_ssd_telemetry(telemetry), expected)
        for generation, speed in enumerate((2.5, 5.0, 8.0, 16.0, 32.0, 64.0), 1):
            self.assertEqual(format_mini_ssd_telemetry({"link_speed": f"{speed} GT/s PCIe"}), f"Gen{generation}")
        presence = self.snapshot().by_id(CapabilityId.MINI_SSD_PRESENCE.value)
        presence.observed_value.clear()
        presence.observed_value.update(state="NVME_PRESENT", pci_address=self.address, controller="nvme0")
        self.assertEqual(format_observed_value(presence), "NVME_PRESENT • Slot 0000:c4:00.0 • (nvme0)")

    def test_gtk_card_renders_telemetry_and_reliability_banner(self):
        Adw.init()
        snapshot = self.snapshot()
        card = MiniSsdStatusCard(
            snapshot.by_id(CapabilityId.MINI_SSD_PRESENCE.value),
            snapshot.by_id(CapabilityId.MINI_SSD_RELIABILITY.value),
        )
        labels = []

        def collect_labels(widget):
            if isinstance(widget, Gtk.Label):
                labels.append(widget.get_text())
            child = widget.get_first_child()
            while child:
                collect_labels(child)
                child = child.get_next_sibling()

        collect_labels(card)
        self.assertTrue(any("Gen4 x2 · 46.9 °C" in label for label in labels))
        self.assertIn(
            "Reliability: NOT_QUALIFIED\nDo not use the Mini SSD as the only copy of important data until reliability qualification passes.",
            labels,
        )


if __name__ == "__main__":
    unittest.main()
