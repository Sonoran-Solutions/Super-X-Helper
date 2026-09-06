from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from superx_helper.capabilities import find_hwmon_by_name
from superx_helper.platform import OperationResult, PlatformBackend


class PlatformTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        hwmon = self.root / "sys/class/hwmon/hwmon5"
        hwmon.mkdir(parents=True)
        (hwmon / "name").write_text("oxpec\n")
        (hwmon / "pwm1").write_text("128\n")
        (hwmon / "pwm1_enable").write_text("2\n")
        cpu = self.root / "sys/devices/system/cpu/cpufreq"
        policy = cpu / "policy0"
        policy.mkdir(parents=True)
        (cpu / "boost").write_text("1\n")
        (policy / "energy_performance_preference").write_text("balance_performance\n")
        (policy / "energy_performance_available_preferences").write_text("default performance balance_performance balance_power power\n")
        backlight = self.root / "sys/class/backlight/amdgpu_bl1"
        backlight.mkdir(parents=True)
        (backlight / "brightness").write_text("250000\n")
        (backlight / "max_brightness").write_text("500000\n")
        (self.root / "sys/bus/pci/devices").mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def test_find_hwmon_by_name(self):
        result = find_hwmon_by_name("oxpec", str(self.root / "sys/class/hwmon"))
        self.assertIsNotNone(result)
        self.assertEqual(result.name, "hwmon5")

    def test_discovery_does_not_authorize_writes(self):
        backend = PlatformBackend(sysfs_root=str(self.root))
        self.assertTrue(backend.capabilities.has_cpu_boost)
        before = Path(backend.capabilities.cpu_boost_path).read_text()
        result = backend.set_cpu_boost(False)
        self.assertFalse(result.success)
        self.assertIn("not production-authorized", result.error_message)
        self.assertEqual(Path(backend.capabilities.cpu_boost_path).read_text(), before)

    def test_authorized_fake_write(self):
        backend = PlatformBackend(sysfs_root=str(self.root), authorized_writes={"cpu_boost"})
        result = backend.set_cpu_boost(False)
        self.assertTrue(result.success)
        self.assertFalse(result.observed_value)

    def test_requested_vs_observed_mismatch_fails(self):
        target = self.root / "target"
        target.write_text("0\n")
        backend = PlatformBackend(sysfs_root=str(self.root), authorized_writes={"test_write"})
        original_read = Path.read_text
        def wrong_read(path, *args, **kwargs):
            if path == target:
                return "different\n"
            return original_read(path, *args, **kwargs)
        with patch.object(Path, "read_text", wrong_read):
            result = backend._safe_write(str(target), "expected", "test_write")
        self.assertFalse(result.success)
        self.assertEqual(result.observed_value, "different")
        self.assertIn("did not verify", result.error_message)

    def test_failed_manual_mode_prevents_fan_duty_write(self):
        backend = PlatformBackend(sysfs_root=str(self.root), authorized_writes={"fan_control"})
        calls = []
        def fake_safe_write(path, value, capability):
            calls.append(capability)
            if capability == "fan_manual_enable":
                return OperationResult(False, capability, value, error_message="mode failed")
            self.fail("fan duty write should not occur after mode failure")
        with patch.object(backend, "_safe_write", side_effect=fake_safe_write):
            result = backend.set_fan_duty(50)
        self.assertFalse(result.success)
        self.assertEqual(calls, ["fan_manual_enable"])
        self.assertIn("Refusing fan-duty write", result.error_message)

    def test_range_checks_remain_before_write(self):
        backend = PlatformBackend(sysfs_root=str(self.root))
        self.assertFalse(backend.set_fan_duty(-1).success)
        self.assertFalse(backend.set_fan_duty(101).success)
        self.assertFalse(backend.set_display_brightness_percent(-1).success)
        self.assertFalse(backend.set_display_brightness_percent(101).success)


if __name__ == "__main__":
    unittest.main()
