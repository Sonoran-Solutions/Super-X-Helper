#!/usr/bin/env python3
"""Unit tests for superx_helper.collector."""

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from superx_helper.collector import (
    _read_sysfs_int,
    _read_sysfs_text,
    collect_all,
    format_summary,
    get_dmi_info,
    get_hwmon_info,
    get_os_kernel_info,
)


class TestCollector(unittest.TestCase):
    def test_read_sysfs_text_missing(self):
        self.assertIsNone(_read_sysfs_text("/nonexistent/sysfs/path"))

    def test_read_sysfs_int_valid(self):
        with tempfile.NamedTemporaryFile("w", delete=False) as f:
            f.write("42\n")
            f_path = f.name
        try:
            self.assertEqual(_read_sysfs_int(f_path), 42)
        finally:
            os.remove(f_path)

    def test_read_sysfs_int_invalid(self):
        with tempfile.NamedTemporaryFile("w", delete=False) as f:
            f.write("not_a_number\n")
            f_path = f.name
        try:
            self.assertIsNone(_read_sysfs_int(f_path))
        finally:
            os.remove(f_path)

    def test_get_dmi_info_mocked(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            dmi_dir = Path(tmpdir)
            (dmi_dir / "sys_vendor").write_text("ONE-NETBOOK\n")
            (dmi_dir / "product_name").write_text("ONEXPLAYER SUPER X\n")
            (dmi_dir / "board_name").write_text("ONEXPLAYER SUPER X\n")
            (dmi_dir / "bios_version").write_text("V1.01\n")

            dmi = get_dmi_info(base_path=str(dmi_dir))
            self.assertEqual(dmi["sys_vendor"], "ONE-NETBOOK")
            self.assertEqual(dmi["product_name"], "ONEXPLAYER SUPER X")
            self.assertEqual(dmi["bios_version"], "V1.01")
            self.assertIsNone(dmi["board_vendor"])

    def test_get_hwmon_info_mocked(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            hw_base = Path(tmpdir)
            hw0 = hw_base / "hwmon0"
            hw0.mkdir()
            (hw0 / "name").write_text("k10temp\n")
            (hw0 / "temp1_input").write_text("55000\n")
            (hw0 / "temp1_label").write_text("Tctl\n")

            sensors = get_hwmon_info(sysfs_hwmon=str(hw_base))
            self.assertEqual(len(sensors), 1)
            self.assertEqual(sensors[0]["name"], "k10temp")
            self.assertEqual(sensors[0]["readings"]["Tctl"]["temp_c"], 55.0)

    def test_collect_all_runs_without_exception(self):
        # On the live machine, collect_all must succeed and return a dict
        data = collect_all()
        self.assertIsInstance(data, dict)
        self.assertIn("timestamp_utc", data)
        self.assertIn("dmi", data)
        self.assertIn("storage", data)
        self.assertIn("cpu", data)

        # Ensure JSON serializable
        serialized = json.dumps(data)
        self.assertTrue(len(serialized) > 0)

        # Ensure summary formatting works
        summary = format_summary(data)
        self.assertIn("ONEXPLAYER Super X", summary)


if __name__ == "__main__":
    unittest.main()
