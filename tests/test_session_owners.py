import unittest
from unittest.mock import Mock, patch

from gi.repository import Gio, GLib

from superx_helper.capabilities import PlatformCapabilities
from superx_helper.contracts import CapabilityId, CapabilityStatus, SafetyState
from superx_helper.service import SuperXService, build_capability_records
from superx_helper.session_owners import GsdBrightnessOwner, PowerProfilesOwner

try:  # package-relative under `-m unittest tests.x`, bare under `discover -s tests`
    from .fake_bus import FakeBus
except ImportError:
    from fake_bus import FakeBus


class SessionOwnerTests(unittest.TestCase):
    def setUp(self):
        # Any accidental use of a real bus fails the test immediately.
        self.bus_guard = patch("superx_helper.session_owners.Gio.bus_get_sync", side_effect=AssertionError("real bus"))
        self.bus_guard.start()
        self.addCleanup(self.bus_guard.stop)
        self.bus = FakeBus()
        self.ppd = PowerProfilesOwner(self.bus)
        self.brightness = GsdBrightnessOwner(self.bus)

    def test_reads_are_fresh_and_use_correct_owners(self):
        self.assertEqual(self.ppd.read(), "balanced")
        self.bus.values["ActiveProfile"] = GLib.Variant("s", "power-saver")
        self.assertEqual(self.ppd.read(), "power-saver")
        self.assertEqual(self.brightness.read(), 50)
        self.assertEqual(self.bus.calls[0][:3], (
            self.ppd.name, self.ppd.path, "org.freedesktop.DBus.Properties",
        ))
        self.assertEqual(self.bus.calls[-1][4].unpack()[0], self.brightness.iface)

    def test_read_bus_errors_are_unavailable(self):
        self.bus.error = GLib.Error("owner unavailable")
        self.assertIsNone(self.ppd.read())
        self.assertIsNone(self.brightness.read())
        self.assertEqual(self.ppd.profiles(), [])
        self.assertEqual(self.ppd.status(), {})

    def test_unavailable_owner_set_fails(self):
        self.bus.error = GLib.Error("owner unavailable")
        for owner, value in ((self.ppd, "balanced"), (self.brightness, 50)):
            result = owner.set(value)
            self.assertFalse(result.success)
            self.assertTrue(result.error_message)
        self.assertEqual(self.bus.sets(), [])
        with patch("superx_helper.session_owners.Gio.bus_get_sync", side_effect=self.bus.error):
            self.assertIsNone(PowerProfilesOwner().read())
            self.assertIsNone(GsdBrightnessOwner().read())

    def test_bus_is_resolved_lazily_with_correct_type(self):
        with patch("superx_helper.session_owners.Gio.bus_get_sync", return_value=self.bus) as get_bus:
            for owner_class, bus_type in ((PowerProfilesOwner, Gio.BusType.SYSTEM), (GsdBrightnessOwner, Gio.BusType.SESSION)):
                owner = owner_class()
                get_bus.reset_mock()
                get_bus.assert_not_called()
                owner.read()
                owner.read()
                get_bus.assert_called_once_with(bus_type, None)

    def test_profiles_and_status(self):
        self.assertEqual(self.ppd.profiles(), ["power-saver", "balanced", "performance"])
        self.assertEqual(self.ppd.status(), {
            "PerformanceDegraded": "", "PerformanceInhibited": "", "ActiveProfileHolds": [],
        })

    def test_ppd_set_success(self):
        result = self.ppd.set("power-saver")
        self.assertTrue(result.success)
        self.assertEqual(result.capability, CapabilityId.CPU_EPP.value)
        self.assertEqual(result.observed_value, "power-saver")
        self.assertEqual(self.bus.calls[-1][3], "Get")
        self.assertEqual(self.bus.sets()[0][4].get_child_value(2).get_variant().get_type_string(), "s")

    def test_invalid_profile_never_sets(self):
        for value in ("balance_performance", True, 50, None):
            self.assertFalse(self.ppd.set(value).success)
        self.assertEqual(self.bus.sets(), [])

    def test_profile_mismatch_fails(self):
        self.bus.apply_set = False
        result = self.ppd.set("performance")
        self.assertFalse(result.success)
        self.assertEqual(result.observed_value, "balanced")
        self.assertIn("read-back mismatch", result.error_message)

    def test_invalid_brightness_never_touches_bus(self):
        for value in (4, 101, True, "50", 55.5, None, float("nan"), float("inf")):
            with self.subTest(value=value):
                self.assertFalse(self.brightness.set(value).success)
        self.assertEqual(self.bus.calls, [])

    def test_brightness_accepts_floor_ceiling_and_integer_float(self):
        for value in (5, 100, 50.0):
            result = self.brightness.set(value)
            self.assertTrue(result.success)
            self.assertEqual(result.observed_value, value)
            self.assertEqual(result.capability, CapabilityId.DISPLAY_BRIGHTNESS.value)
            self.assertEqual(self.bus.sets()[-1][4].get_child_value(2).get_variant().get_type_string(), "i")

    @patch("superx_helper.session_owners.time.sleep")
    def test_brightness_async_readback(self, sleep):
        self.bus.brightness_reads = [50, 50, 50, 75]
        result = self.brightness.set(75)
        self.assertTrue(result.success)
        self.assertEqual(result.observed_value, 75)
        self.assertEqual(sleep.call_count, 2)

    @patch("superx_helper.session_owners.time.sleep")
    def test_brightness_mismatch_fails(self, sleep):
        self.bus.apply_set = False
        result = self.brightness.set(75)
        self.assertFalse(result.success)
        self.assertEqual(result.observed_value, 50)
        self.assertIn("read-back mismatch", result.error_message)
        self.assertEqual(sleep.call_count, 10)

    def test_no_backlight_does_not_set(self):
        self.bus.values["Brightness"] = GLib.Variant("i", -1)
        self.assertFalse(self.brightness.set(50).success)
        self.assertEqual(self.bus.sets(), [])

    def test_set_and_readback_errors_fail(self):
        for owner, value in ((self.ppd, "performance"), (self.brightness, 75)):
            with self.subTest(owner=type(owner).__name__):
                self.bus.error = GLib.Error("permission denied")
                self.bus.error_method = "Set"
                result = owner.set(value)
                self.assertFalse(result.success)
                self.assertIn("permission denied", result.error_message)
                self.bus.error = None
                original = self.bus.call_sync

                def fail_after_set(*args):
                    reply = original(*args)
                    if args[3] == "Set":
                        self.bus.error = GLib.Error("owner vanished")
                        self.bus.error_method = "Get"
                    return reply

                with patch.object(self.bus, "call_sync", side_effect=fail_after_set):
                    result = owner.set(value)
                self.assertFalse(result.success)
                self.assertIn("owner vanished", result.error_message)
                self.bus.error = None


class OwnerServiceTests(unittest.TestCase):
    def setUp(self):
        guard = patch("superx_helper.session_owners.Gio.bus_get_sync", side_effect=AssertionError("real bus"))
        guard.start()
        self.addCleanup(guard.stop)
        self.bus = FakeBus()
        self.ppd = PowerProfilesOwner(self.bus)
        self.brightness = GsdBrightnessOwner(self.bus)
        self.platform = Mock()
        self.platform.read_epp.return_value = "balance_performance"
        self.platform.read_display_brightness_percent.return_value = 80.0
        self.low = PlatformCapabilities(has_epp_control=True, has_backlight_control=True)
        self.ids = {CapabilityId.CPU_EPP.value, CapabilityId.DISPLAY_BRIGHTNESS.value}

    def records(self, validated=()):
        return {record.capability_id: record for record in build_capability_records(
            self.low, self.platform, validated_writes=validated,
            power_profiles=self.ppd, brightness_owner=self.brightness,
        )}

    def service(self, validated=()):
        return SuperXService(self.platform, validated, self.ppd, self.brightness)

    def test_owner_records_authorization_gate(self):
        for validated in ((), self.ids):
            records = self.records(validated)
            for cid in self.ids:
                record = records[cid]
                self.assertEqual(record.can_write, bool(validated))
                self.assertEqual(record.write_authorized, bool(validated))
                self.assertEqual(record.locally_validated, bool(validated))
                self.assertEqual(record.status, CapabilityStatus.CONFIRMED_LOCAL if validated else CapabilityStatus.SUPPORTED_UNVERIFIED)
                self.assertEqual(record.safety_state, SafetyState.NORMAL if validated else SafetyState.WARNING)
            epp = records[CapabilityId.CPU_EPP.value]
            self.assertEqual((epp.label, epp.observed_value, epp.owner, epp.backend), (
                "Power Profile (EPP)", "balanced", "power-profiles-daemon", "power_profiles",
            ))
            self.assertEqual(epp.allowed_values, self.ppd.profiles())
            self.assertIn("Drives amd-pstate EPP (currently balance_performance).", epp.warnings)
            bright = records[CapabilityId.DISPLAY_BRIGHTNESS.value]
            self.assertEqual((bright.observed_value, bright.minimum, bright.maximum, bright.unit), (50, 5, 100, "%"))
            self.assertEqual((bright.owner, bright.backend), ("gnome-settings-daemon", "session_brightness"))

    def test_owner_warnings(self):
        self.bus.values.update({
            "PerformanceDegraded": GLib.Variant("s", "high-operating-temperature"),
            "PerformanceInhibited": GLib.Variant("s", "lap-detected"),
            "ActiveProfileHolds": GLib.Variant("aa{sv}", [{"Profile": GLib.Variant("s", "balanced")}]),
        })
        record = self.records(self.ids)[CapabilityId.CPU_EPP.value]
        self.assertEqual(record.safety_state, SafetyState.WARNING)
        for prop in ("PerformanceDegraded", "PerformanceInhibited", "ActiveProfileHolds"):
            self.assertTrue(any(prop in warning for warning in record.warnings))

    def test_unavailable_owners_never_authorize_sysfs(self):
        self.bus.error = GLib.Error("unavailable")
        records = self.records(self.ids)
        for cid in self.ids:
            record = records[cid]
            self.assertFalse(record.can_write)
            self.assertFalse(record.write_authorized)
            self.assertFalse(record.locally_validated)
            self.assertEqual(record.status, CapabilityStatus.SUPPORTED_UNVERIFIED)
            self.assertEqual(record.backend, "platform")
            self.assertIn("not an authorized path", record.reason_unavailable)

    def test_no_backlight_falls_back_read_only(self):
        self.bus.values["Brightness"] = GLib.Variant("i", -1)
        record = self.records(self.ids)[CapabilityId.DISPLAY_BRIGHTNESS.value]
        self.assertFalse(record.can_write)
        self.assertEqual(record.observed_value, 80.0)

    def test_owner_works_without_sysfs_control(self):
        self.low = PlatformCapabilities()
        for cid in self.ids:
            self.assertTrue(self.records(self.ids)[cid].can_write)

    def test_dispatches_only_to_owners(self):
        service = self.service(self.ids)
        self.assertTrue(service.set_capability(CapabilityId.CPU_EPP, "power-saver").success)
        self.assertTrue(service.set_capability(CapabilityId.DISPLAY_BRIGHTNESS, 75).success)
        self.platform.set_epp.assert_not_called()
        self.platform.set_display_brightness_percent.assert_not_called()
        self.assertEqual(len(self.bus.sets()), 2)

    def test_snapshot_passes_owners_and_authorization(self):
        self.platform.refresh_capabilities.return_value = self.low
        self.platform.sysfs_root = "/unused-fixture"
        with patch("superx_helper.service.get_battery_info", return_value={}), patch(
            "superx_helper.service.get_display_info", return_value={}
        ), patch("superx_helper.service.read_mini_ssd_telemetry", return_value={}):
            snapshot = self.service(self.ids).get_capability_snapshot()
        self.assertEqual(snapshot.by_id(CapabilityId.CPU_EPP.value).observed_value, "balanced")
        self.assertEqual(snapshot.by_id(CapabilityId.DISPLAY_BRIGHTNESS.value).observed_value, 50)
        for cid in self.ids:
            self.assertTrue(snapshot.by_id(cid).can_write)

    def test_unavailable_dispatch_never_uses_sysfs(self):
        self.bus.error = GLib.Error("unavailable")
        service = self.service(self.ids)
        for cid, value in ((CapabilityId.CPU_EPP, "balanced"), (CapabilityId.DISPLAY_BRIGHTNESS, 50)):
            result = service.set_capability(cid, value)
            self.assertFalse(result.success)
            self.assertIn("unavailable", result.error_message)
        self.platform.set_epp.assert_not_called()
        self.platform.set_display_brightness_percent.assert_not_called()
        self.assertEqual(self.bus.sets(), [])

    def test_no_backlight_dispatch_never_uses_sysfs(self):
        self.bus.values["Brightness"] = GLib.Variant("i", -1)
        result = self.service(self.ids).set_capability(CapabilityId.DISPLAY_BRIGHTNESS, 50)
        self.assertFalse(result.success)
        self.platform.set_display_brightness_percent.assert_not_called()
        self.assertEqual(self.bus.sets(), [])

    def test_unauthorized_dispatch_never_touches_bus(self):
        service = self.service()
        for cid in self.ids:
            self.assertFalse(service.set_capability(cid, 50).success)
        self.assertEqual(self.bus.calls, [])


if __name__ == "__main__":
    unittest.main()
