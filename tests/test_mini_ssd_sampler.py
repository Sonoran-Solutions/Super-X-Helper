import datetime
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from superx_helper import collector, mini_ssd_sampler


class FakeSysfsCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.log = self.root / "state" / "superx-helper" / "mini-ssd-telemetry.jsonl"
        address = "0000:c4:00.0"
        pci = self.root / "sys/devices/pci0000:00/0000:00:03.1" / address
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



class SamplerTests(FakeSysfsCase):
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
        datetime.datetime.fromisoformat(row["timestamp_utc"])

    def test_absent_drive_still_logs_a_row(self):
        mini_ssd_sampler.main(["--sysfs-root", str(self.root / "nowhere"), "-o", str(self.log)])
        row = json.loads(self.lines()[0])
        self.assertEqual((row["state"], row["link_speed"], row["temperature_c"]), ("ABSENT", None, None))

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

