#!/usr/bin/env python3
"""Unit tests for superx_helper.capabilities and superx_helper.platform."""

from pathlib import Path
import tempfile
import unittest

from superx_helper.capabilities import detect_capabilities, find_hwmon_by_name
from superx_helper.platform import PlatformBackend


class TestCapabilitiesAndPlatform(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)

        # Setup mock sysfs tree
        self.hwmon_dir = self.root / "sys/class/hwmon"
        self.hwmon_dir.mkdir(parents=True)

        # Mock oxpec hwmon
        oxp = self.hwmon_dir / "hwmon5"
        oxp.mkdir()
        (oxp / "name").write_text("oxpec\n")
        (oxp / "pwm1").write_text("128\n")
        (oxp / "pwm1_enable").write_text("2\n")

        # Mock cpufreq
        cpufreq_dir = self.root / "sys/devices/system/cpu/cpufreq"
        policy0 = cpufreq_dir / "policy0"
        policy0.mkdir(parents=True)
        (cpufreq_dir / "boost").write_text("1\n")
        (policy0 / "energy_performance_preference").write_text("balance_performance\n")
        (policy0 / "energy_performance_available_preferences").write_text(
            "default performance balance_performance power\n"
        )

        # Mock backlight
        bl_dir = self.root / "sys/class/backlight/amdgpu_bl1"
        bl_dir.mkdir(parents=True)
        (bl_dir / "brightness").write_text("250000\n")
        (bl_dir / "max_brightness").write_text("500000\n")

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_find_hwmon_by_name(self):
        res = find_hwmon_by_name("oxpec", sysfs_hwmon=str(self.hwmon_dir))
        self.assertIsNotNone(res)
        self.assertEqual(res.name, "hwmon5")

        res_none = find_hwmon_by_name("nonexistent", sysfs_hwmon=str(self.hwmon_dir))
        self.assertIsNone(res_none)

    def test_detect_capabilities(self):
        caps = detect_capabilities(sysfs_root=str(self.root))
        self.assertTrue(caps.has_fan_control)
        self.assertTrue(caps.oxpec_driver_loaded)
        self.assertEqual(caps.fan_hwmon_name, "oxpec")
        self.assertTrue(caps.has_cpu_boost)
        self.assertTrue(caps.has_epp_control)
        self.assertIn("performance", caps.epp_available_preferences)
        self.assertTrue(caps.has_backlight_control)
        self.assertEqual(caps.backlight_max, 500000)

    def test_platform_fan_range_and_control(self):
        backend = PlatformBackend(sysfs_root=str(self.root), dry_run=False)

        # Out of bounds duty cycle
        res_invalid_high = backend.set_fan_duty(105)
        self.assertFalse(res_invalid_high.success)
        self.assertIn("out of valid range", res_invalid_high.error_message)

        res_invalid_low = backend.set_fan_duty(-10)
        self.assertFalse(res_invalid_low.success)

        # Valid duty cycle (50%) -> should write ~128 to pwm1
        res_valid = backend.set_fan_duty(50)
        self.assertTrue(res_valid.success)
        # Read back duty
        current_duty = backend.read_fan_duty()
        self.assertIsNotNone(current_duty)
        self.assertEqual(current_duty, 50)

    def test_platform_epp_validation(self):
        backend = PlatformBackend(sysfs_root=str(self.root), dry_run=False)

        # Invalid preference
        res_invalid = backend.set_epp("ultra_hyper_mode")
        self.assertFalse(res_invalid.success)
        self.assertIn("invalid", res_invalid.error_message)

        # Valid preference
        res_valid = backend.set_epp("performance")
        self.assertTrue(res_valid.success)
        self.assertEqual(backend.read_epp(), "performance")

    def test_platform_brightness_control(self):
        backend = PlatformBackend(sysfs_root=str(self.root), dry_run=False)

        # Range checks
        self.assertFalse(backend.set_display_brightness_percent(-1.0).success)
        self.assertFalse(backend.set_display_brightness_percent(101.0).success)

        # Valid set 80%
        res = backend.set_display_brightness_percent(80.0)
        self.assertTrue(res.success)
        read_pct = backend.read_display_brightness_percent()
        self.assertIsNotNone(read_pct)
        self.assertEqual(read_pct, 80.0)

    def test_dry_run_mode(self):
        backend = PlatformBackend(sysfs_root=str(self.root), dry_run=True)
        res = backend.set_cpu_boost(False)
        self.assertTrue(res.success)
        self.assertTrue(res.dry_run)
        # Verify file content did NOT change on disk in dry run
        boost_content = Path(backend.capabilities.cpu_boost_path).read_text().strip()
        self.assertEqual(boost_content, "1")


if __name__ == "__main__":
    unittest.main()
