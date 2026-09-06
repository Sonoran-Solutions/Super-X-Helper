import json
from pathlib import Path
import tempfile
import unittest

from superx_helper.collector import _redacted, _read_sysfs_int, _read_sysfs_text, get_dmi_info, get_hwmon_info


class CollectorTests(unittest.TestCase):
    def test_read_helpers(self):
        with tempfile.NamedTemporaryFile("w", delete=False) as handle:
            handle.write("42\n")
            path = handle.name
        try:
            self.assertEqual(_read_sysfs_text(path), "42")
            self.assertEqual(_read_sysfs_int(path), 42)
        finally:
            Path(path).unlink()

    def test_missing_read(self):
        self.assertIsNone(_read_sysfs_text("/definitely/not/here"))

    def test_dmi_mock(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "sys_vendor").write_text("ONE-NETBOOK\n")
            (base / "product_name").write_text("ONEXPLAYER SUPER X\n")
            data = get_dmi_info(str(base))
            self.assertEqual(data["sys_vendor"], "ONE-NETBOOK")
            self.assertEqual(data["product_name"], "ONEXPLAYER SUPER X")

    def test_hwmon_mock(self):
        with tempfile.TemporaryDirectory() as tmp:
            hw = Path(tmp) / "hwmon0"
            hw.mkdir()
            (hw / "name").write_text("k10temp\n")
            (hw / "temp1_input").write_text("55000\n")
            (hw / "temp1_label").write_text("Tctl\n")
            data = get_hwmon_info(tmp)
            self.assertEqual(data[0]["readings"]["Tctl"]["temp_c"], 55.0)

    def test_identifier_redaction_is_default_safe(self):
        self.assertEqual(_redacted("ABC123", False), "REDACTED")
        self.assertEqual(_redacted("ABC123", True), "ABC123")
        self.assertIsNone(_redacted(None, False))


if __name__ == "__main__":
    unittest.main()
