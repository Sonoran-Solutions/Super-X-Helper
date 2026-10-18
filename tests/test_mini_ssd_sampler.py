import datetime
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from superx_helper import collector, mini_ssd_sampler
from superx_helper.storage import read_mini_ssd_power_state, read_namespace_io


class FakeSysfsCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.log = self.root / "state" / "superx-helper" / "mini-ssd-telemetry.jsonl"
        address = "0000:c4:00.0"
        pci = self.root / "sys/devices/pci0000:00/0000:00:03.1" / address
        self.address = address
        self.pci = pci
        nvme = pci / "nvme" / "nvme0"
        (nvme / "nvme0n1").mkdir(parents=True)
        (pci / "vendor").write_text("0x1dee")
        (pci / "device").write_text("0x2268")
        (pci / "link").mkdir()
        for name, value in (("current_link_speed", "16.0 GT/s PCIe"), ("current_link_width", "2"),
                            ("max_link_speed", "16.0 GT/s PCIe"), ("max_link_width", "2")):
            (pci / name).write_text(value + "\n")
        for name in ("l1_aspm", "l1_1_aspm", "l1_2_aspm"):
            (pci / "link" / name).write_text("1\n")
        for name in ("l1_1_pcipm", "l1_2_pcipm", "clkpm"):
            (pci / "link" / name).write_text("1\n")
        (pci / "d3cold_allowed").write_text("1\n")
        (pci / "power").mkdir()
        (pci / "power/runtime_status").write_text("active\n")
        self.stat = self.root / "sys/block/nvme0n1/stat"
        self.stat.parent.mkdir(parents=True)
        self.stat.write_text(
            "   82829     1924 14411266    17996       19       12      248"
            "      101        0    13240    18100        0        0        0        0        5        2\n"
        )
        self.mountinfo = self.root / "proc/self/mountinfo"
        self.mountinfo.parent.mkdir(parents=True)
        self.mountinfo.write_text(
            "412 29 259:1 / /media/someuser/MiniSSD rw,nosuid,nodev,relatime "
            "shared:229 - ext4 /dev/nvme0n1p1 rw\n"
        )
        bus = self.root / "sys/bus/pci/devices"
        bus.mkdir(parents=True)
        (bus / address).symlink_to(pci, target_is_directory=True)
        hwmon = self.root / "sys/class/hwmon/hwmon4"
        hwmon.mkdir(parents=True)
        (hwmon / "name").write_text("nvme\n")
        (hwmon / "device").symlink_to(nvme, target_is_directory=True)
        (hwmon / "temp1_input").write_text("46850")

    def lines(self):
        return self.log.read_text().splitlines()



class StorageReadTests(FakeSysfsCase):
    def test_power_state(self):
        self.assertEqual(read_mini_ssd_power_state(self.address, str(self.root)), {
            "l1_1_pcipm": True, "l1_2_pcipm": True, "clkpm": True,
            "d3cold_allowed": True, "runtime_status": "active",
        })

    def test_power_flags_zero_or_invalid(self):
        for value, expected in (("0\n", False), ("2", None), ("garbled", None), ("", None)):
            with self.subTest(value=value):
                for path in ("link/l1_1_pcipm", "link/l1_2_pcipm", "link/clkpm", "d3cold_allowed"):
                    (self.pci / path).write_text(value)
                power = read_mini_ssd_power_state(self.address, str(self.root))
                self.assertEqual(power, {
                    "l1_1_pcipm": expected, "l1_2_pcipm": expected, "clkpm": expected,
                    "d3cold_allowed": expected, "runtime_status": "active",
                })

    def test_power_missing_files_or_pci(self):
        for path in ("link/l1_1_pcipm", "link/l1_2_pcipm", "link/clkpm",
                     "d3cold_allowed", "power/runtime_status"):
            (self.pci / path).unlink()
        empty = dict.fromkeys(("l1_1_pcipm", "l1_2_pcipm", "clkpm", "d3cold_allowed", "runtime_status"))
        for address in (self.address, "0000:ff:00.0", None):
            with self.subTest(address=address):
                self.assertEqual(read_mini_ssd_power_state(address, str(self.root)), empty)

    def test_power_unreadable_files(self):
        for error in (PermissionError(), UnicodeError()):
            with self.subTest(error=type(error)), patch.object(Path, "read_text", side_effect=error):
                power = read_mini_ssd_power_state(self.address, str(self.root))
                self.assertTrue(all(value is None for value in power.values()))

    def test_namespace_io_real_stat(self):
        self.assertEqual(read_namespace_io("nvme0n1", str(self.root)), {
            "namespace": "nvme0n1", "reads_completed": 82829, "sectors_read": 14411266,
            "writes_completed": 19, "sectors_written": 248, "mounted": True,
        })

    def test_namespace_io_missing_stat(self):
        self.stat.unlink()
        self.assertEqual(read_namespace_io("nvme0n1", str(self.root)), {
            "namespace": "nvme0n1", "reads_completed": None, "sectors_read": None,
            "writes_completed": None, "sectors_written": None, "mounted": True,
        })

    def test_namespace_io_short_or_garbled_stat(self):
        for stat, expected in (("1 0 broken 0 2 0", [1, None, 2, None]),
                               ("", [None] * 4), ("bad 0 bad 0 bad 0 bad", [None] * 4)):
            with self.subTest(stat=stat):
                self.stat.write_text(stat)
                io = read_namespace_io("nvme0n1", str(self.root))
                self.assertEqual([io[key] for key in (
                    "reads_completed", "sectors_read", "writes_completed", "sectors_written"
                )], expected)
                self.assertTrue(io["mounted"])

    def test_namespace_mount_sources_match_exactly(self):
        for source, mounted in (("/dev/nvme0n1p1", True), ("/dev/nvme0n1", True),
                                ("/dev/nvme1n1p2", False), ("/dev/nvme0n10", False),
                                ("/dev/nvme0n1p", False), ("/dev/nvme0n1p1extra", False)):
            with self.subTest(source=source):
                self.mountinfo.write_text(
                    "12 1 0:1 / / rw - tmpfs tmpfs rw\n"
                    f"412 29 259:1 / /media/someuser/MiniSSD rw shared:229 - ext4 {source} rw\n"
                )
                self.assertIs(read_namespace_io("nvme0n1", str(self.root))["mounted"], mounted)

    def test_namespace_missing_or_empty_mountinfo(self):
        self.mountinfo.write_text("")
        self.assertIs(read_namespace_io("nvme0n1", str(self.root))["mounted"], False)
        self.mountinfo.unlink()
        self.assertIsNone(read_namespace_io("nvme0n1", str(self.root))["mounted"])

    def test_namespace_unreadable_files(self):
        self.stat.write_bytes(b"\xff")
        self.mountinfo.write_bytes(b"\xff")
        self.assertEqual(read_namespace_io("nvme0n1", str(self.root)), {
            "namespace": "nvme0n1", "reads_completed": None, "sectors_read": None,
            "writes_completed": None, "sectors_written": None, "mounted": None,
        })

    def test_no_namespace(self):
        self.assertIsNone(read_namespace_io(None, str(self.root)))


class SamplerTests(FakeSysfsCase):
    def test_sample_preserves_existing_fields_and_excludes_mount_details(self):
        now = datetime.datetime(2026, 10, 18, tzinfo=datetime.timezone.utc)
        sample = mini_ssd_sampler.take_sample(str(self.root), now)
        self.assertEqual(sample, {
            "timestamp_utc": "2026-10-18T00:00:00+00:00", "state": "NVME_PRESENT",
            "pci_address": self.address, "controller": "nvme0",
            "link_speed": "16.0 GT/s PCIe", "link_width": 2,
            "max_link_speed": "16.0 GT/s PCIe", "max_link_width": 2,
            "aspm": {"l1": True, "l1_1": True, "l1_2": True}, "temperature_c": 46.9,
            "power": {"l1_1_pcipm": True, "l1_2_pcipm": True, "clkpm": True,
                      "d3cold_allowed": True, "runtime_status": "active"},
            "io": {"namespace": "nvme0n1", "reads_completed": 82829, "sectors_read": 14411266,
                   "writes_completed": 19, "sectors_written": 248, "mounted": True},
        })
        serialized = json.dumps(sample)
        for private in ("someuser", "/media", "nosuid", "shared:229", "ext4", "/dev/"):
            self.assertNotIn(private, serialized)

    def test_main_appends_one_json_line_per_run(self):
        for _ in range(2):
            self.assertEqual(mini_ssd_sampler.main(["--sysfs-root", str(self.root), "-o", str(self.log)]), 0)
        rows = [json.loads(line) for line in self.lines()]
        self.assertEqual(len(rows), 2)
        row = rows[0]
        self.assertEqual(row["state"], "NVME_PRESENT")
        self.assertEqual(row["controller"], "nvme0")
        self.assertEqual((row["link_speed"], row["link_width"]), ("16.0 GT/s PCIe", 2))
        self.assertEqual(row["aspm"], {"l1": True, "l1_1": True, "l1_2": True})
        self.assertEqual(row["temperature_c"], 46.9)
        self.assertEqual(row["power"]["runtime_status"], "active")
        self.assertEqual(row["io"]["reads_completed"], 82829)
        self.assertTrue(row["io"]["mounted"])
        datetime.datetime.fromisoformat(row["timestamp_utc"])

    def test_absent_drive_still_logs_a_row(self):
        mini_ssd_sampler.main(["--sysfs-root", str(self.root / "nowhere"), "-o", str(self.log)])
        row = json.loads(self.lines()[0])
        self.assertEqual((row["state"], row["link_speed"], row["temperature_c"]), ("ABSENT", None, None))
        self.assertIsNone(row["io"])
        self.assertTrue(all(value is None for value in row["power"].values()))

    def test_log_is_capped_to_newest_lines(self):
        for i in range(30):
            mini_ssd_sampler.append_sample({"n": i, "pad": "x" * 200}, self.log, max_lines=10)
        rows = [json.loads(line) for line in self.lines()]
        self.assertLessEqual(len(rows), 10)
        self.assertEqual(rows[-1]["n"], 29)
        self.assertEqual(rows[0]["n"], 30 - len(rows))

    def test_default_path_uses_xdg_state_home(self):
        with patch.dict("os.environ", {"XDG_STATE_HOME": str(self.root)}):
            self.assertEqual(mini_ssd_sampler.default_log_path(), self.root / "superx-helper" / "mini-ssd-telemetry.jsonl")


class CollectorLogTests(FakeSysfsCase):
    def setUp(self):
        super().setUp()
        # Keep existing collect_all checks from invoking any host commands.
        commands = patch.object(collector.shutil, "which", return_value=None)
        commands.start()
        self.addCleanup(commands.stop)

    def test_missing_log_is_tolerated(self):
        result = collector.get_mini_ssd_telemetry_log(self.log)
        self.assertFalse(result["available"])
        self.assertEqual(result["samples"], [])
        self.assertEqual(collector.format_summary({"mini_ssd_telemetry_log": result}).count("Mini SSD Samples: no samples"), 1)

    def test_tail_limit_and_bad_lines(self):
        self.log.parent.mkdir(parents=True)
        self.log.write_text("".join(json.dumps({"timestamp_utc": f"t{i}"}) + "\n" for i in range(300)) + "garbage\n")
        result = collector.get_mini_ssd_telemetry_log(self.log, limit=200)
        self.assertEqual(len(result["samples"]), 200)
        self.assertEqual(result["samples"][-1], {"unparsed": "garbage"})

    def test_collect_all_includes_key_and_summary_shows_last_sample(self):
        mini_ssd_sampler.main(["--sysfs-root", str(self.root), "-o", str(self.log)])
        with patch.dict("os.environ", {"XDG_STATE_HOME": str(self.log.parents[1])}), patch.object(
            collector, "get_mini_ssd_boot_events", return_value={"available": False}
        ):
            data = collector.collect_all()
        self.assertEqual(len(data["mini_ssd_telemetry_log"]["samples"]), 1)
        summary = collector.format_summary(data)
        self.assertIn("Mini SSD Samples: 1 (last ", summary)
        self.assertIn("NVME_PRESENT, 16.0 GT/s PCIe x2, 46.9 °C", summary)

    def test_collect_all_without_log(self):
        with patch.dict("os.environ", {"XDG_STATE_HOME": str(self.root / "empty")}), patch.object(
            collector, "get_mini_ssd_boot_events", return_value={"available": False}
        ):
            data = collector.collect_all()
        self.assertFalse(data["mini_ssd_telemetry_log"]["available"])

