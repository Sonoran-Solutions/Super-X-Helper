"""Boundary tests use real GLib Variants/main-loop delivery, never a real bus."""

import json
import threading
import time
import unittest
import xml.etree.ElementTree as ET
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from gi.repository import Gio, GLib

from superx_helper.client import (
    DBusServiceClient, LocalServiceClient, SessionServiceClient, apply_capability_async,
)
from superx_helper.contracts import CapabilityRecord, CapabilitySnapshot, CapabilityStatus, OperationResult
from superx_helper.dbus_service import (
    BUS_NAME, CAPABILITY_ACTIONS, INTERFACE, MAX_VALUE_BYTES, OBJECT_PATH,
    POLKIT_TIMEOUT_MS, DBusService, system_service,
)
from superx_helper.policy import LOCALLY_VALIDATED_WRITES, OWNER_ROUTED_WRITES
from superx_helper.service import SuperXService
from superx_helper.transport import operation_result_from_dict, snapshot_to_dict
from superx_helper.ui.app import select_client
from superx_helper.ui.window import SuperXWindow


def snapshot(value=False):
    return CapabilitySnapshot(1, "fixture", [CapabilityRecord(
        "performance.cpu_boost", "Boost", CapabilityStatus.SUPPORTED_UNVERIFIED,
        read_supported=True, write_supported=True, locally_validated=False, observed_value=value,
    )])


class FakeInvocation:
    def __init__(self):
        self.value = None
        self.error = None

    def return_value(self, value):
        self.value = value

    def return_dbus_error(self, name, message):
        self.error = (name, message)


class BoundaryBus:
    """Loop requests straight through the handler; record polkit separately."""

    def __init__(self, adapter):
        self.adapter = adapter
        self.calls = []
        self.allowed = True
        self.error = None
        self.owned = True

    def call_sync(self, name, path, iface, method, params, reply_type, flags, timeout, cancellable):
        self.calls.append((name, path, iface, method, params, flags, timeout))
        if self.error:
            raise self.error
        if method == "NameHasOwner":
            assert params.unpack() == (BUS_NAME,)
            assert timeout == 2000
            return GLib.Variant("(b)", (self.owned,))
        if method == "CheckAuthorization":
            assert (name, path, iface) == (
                "org.freedesktop.PolicyKit1", "/org/freedesktop/PolicyKit1/Authority",
                "org.freedesktop.PolicyKit1.Authority",
            )
            assert timeout == POLKIT_TIMEOUT_MS
            return GLib.Variant("((bba{ss}))", ((self.allowed, False, {}),))
        assert (name, path, iface) == (BUS_NAME, OBJECT_PATH, INTERFACE)
        assert flags == Gio.DBusCallFlags.NO_AUTO_START
        invocation = FakeInvocation()
        self.adapter.handle_method_call(self, ":1.42", path, iface, method, params, invocation)
        if invocation.error:
            raise GLib.Error(invocation.error[1])
        return invocation.value

    def polkit_calls(self):
        return [call for call in self.calls if call[3] == "CheckAuthorization"]


class DBusBoundaryTests(unittest.TestCase):
    def setUp(self):
        guard = patch.object(Gio, "bus_get_sync", side_effect=AssertionError("real bus"))
        guard.start()
        self.addCleanup(guard.stop)
        self.platform = Mock()
        self.platform.set_cpu_boost.side_effect = lambda value: OperationResult(
            True, "performance.cpu_boost", value, observed_value=value,
        )
        self.platform.set_fan_duty.side_effect = lambda value: OperationResult(
            True, "cooling.internal_fan", value, observed_value=value,
        )
        self.service = SuperXService(
            self.platform, (), power_profiles=Mock(), brightness_owner=Mock(),
        )
        self.snapshot = snapshot()
        self.service.get_capability_snapshot = Mock(return_value=self.snapshot)
        self.adapter = DBusService(self.service)
        self.bus = BoundaryBus(self.adapter)
        self.client = DBusServiceClient(self.bus)

    def invoke(self, cid, raw):
        invocation = FakeInvocation()
        self.adapter.handle_method_call(
            self.bus, ":1.42", OBJECT_PATH, INTERFACE, "SetCapability",
            GLib.Variant("(ss)", (cid, raw)), invocation,
        )
        self.assertIsNone(invocation.error)
        return operation_result_from_dict(json.loads(invocation.value.unpack()[0]))

    def test_snapshot_roundtrip_via_handler(self):
        actual = self.client.get_snapshot()
        self.assertEqual(snapshot_to_dict(actual), snapshot_to_dict(self.snapshot))
        self.service.get_capability_snapshot.assert_called_once_with()
        self.assertEqual(self.bus.polkit_calls(), [])

    def test_register_exposes_only_narrow_methods(self):
        connection = Mock()
        self.adapter.register(connection)
        args = connection.register_object.call_args.args
        self.assertEqual(args[0], OBJECT_PATH)
        self.assertEqual(args[1].name, INTERFACE)
        self.assertEqual({method.name for method in args[1].methods}, {"GetSnapshot", "SetCapability"})
        self.assertEqual(args[2], self.adapter.handle_method_call)

    def test_unknown_ids_do_not_consult_polkit_or_dispatch(self):
        for cid in ("unknown", "performance.cpu_boost.extra", "/sys/fake", ""):
            result = self.invoke(cid, "true")
            self.assertFalse(result.success)
            self.assertIn("Unknown", result.error_message)
        self.assertEqual(self.bus.polkit_calls(), [])
        self.assertEqual(self.platform.mock_calls, [])

    def test_unauthorized_id_uses_service_gate_without_prompt(self):
        with patch.object(self.service, "set_capability", wraps=self.service.set_capability) as setter:
            result = self.invoke("performance.cpu_boost", "true")
        setter.assert_called_once_with("performance.cpu_boost", True)
        self.assertFalse(result.success)
        self.assertIn("not production-authorized", result.error_message)
        self.assertEqual(self.bus.polkit_calls(), [])
        self.assertEqual(self.platform.mock_calls, [])

    def test_known_readonly_ids_have_no_privileged_action(self):
        for cid in ("storage.mini_ssd.presence", "display.mode", "cooling.frost_bay.control"):
            self.assertFalse(self.invoke(cid, "true").success)
        self.assertEqual(self.bus.polkit_calls(), [])

    def test_bad_json_and_size_never_dispatch_or_prompt(self):
        self.service.validated_writes = {"performance.cpu_boost"}
        for raw in ("", "{", "true false", '"' + "x" * MAX_VALUE_BYTES + '"', "[" * 1500):
            with self.subTest(raw=raw[:20]):
                self.assertFalse(self.invoke("performance.cpu_boost", raw).success)
        self.assertEqual(self.bus.polkit_calls(), [])
        self.assertEqual(self.platform.mock_calls, [])

    def test_size_cap_counts_utf8_bytes(self):
        result = self.invoke("performance.epp", '"' + "é" * (MAX_VALUE_BYTES // 2) + '"')
        self.assertIn("4096 bytes", result.error_message)

    def test_types_and_nonfinite_values_fail_before_polkit(self):
        cases = {
            "performance.cpu_boost": ("1", '"true"', "null", "{}", "[]", "NaN", "1e999"),
            "cooling.internal_fan": ("true", '"42"', "42.0", "-1", "101", "Infinity", "-Infinity"),
            "display.brightness": ("true", '"50"', "50.5", "4", "101", "NaN", "1e999"),
            "performance.epp": ("true", "50", "null", "[]"),
        }
        self.service.validated_writes = set(cases)
        for cid, values in cases.items():
            for raw in values:
                with self.subTest(cid=cid, raw=raw):
                    self.assertFalse(self.invoke(cid, raw).success)
        self.assertEqual(self.bus.polkit_calls(), [])
        self.assertEqual(self.platform.mock_calls, [])

    def test_owner_writes_never_reach_root_backend_or_polkit(self):
        # Even accidental facade authorization cannot route these through root.
        self.service.validated_writes = set(OWNER_ROUTED_WRITES)
        for cid, raw in (("performance.epp", '"balanced"'), ("display.brightness", "50.0")):
            result = self.invoke(cid, raw)
            self.assertFalse(result.success)
            self.assertIn("user's session", result.error_message)
        self.service.power_profiles.set.assert_not_called()
        self.service.brightness_owner.set.assert_not_called()
        self.assertEqual(self.bus.polkit_calls(), [])

    def test_polkit_denial_and_unavailable_fail_closed(self):
        self.service.validated_writes = {"performance.cpu_boost"}
        self.bus.allowed = False
        self.assertFalse(self.invoke("performance.cpu_boost", "true").success)
        self.bus.error = GLib.Error("authority unavailable")
        self.assertFalse(self.invoke("performance.cpu_boost", "true").success)
        self.assertEqual(len(self.bus.polkit_calls()), 2)
        self.platform.set_cpu_boost.assert_not_called()

    def test_polkit_subject_and_action_are_fixed_then_service_dispatches(self):
        self.service.validated_writes = {"performance.cpu_boost", "cooling.internal_fan"}
        for cid, raw, expected in (("performance.cpu_boost", "true", True), ("cooling.internal_fan", "42", 42)):
            result = self.invoke(cid, raw)
            self.assertTrue(result.success)
            self.assertEqual(result.observed_value, expected)
            subject, action, details, flags, cancellation = self.bus.polkit_calls()[-1][4].unpack()
            self.assertEqual(subject, ("system-bus-name", {"name": ":1.42"}))
            self.assertEqual(action, CAPABILITY_ACTIONS[cid])
            self.assertEqual((details, flags, cancellation), ({}, 1, ""))

    def test_facade_authorization_is_rechecked_after_polkit(self):
        self.service.validated_writes = {"performance.cpu_boost"}

        def revoke(*args):
            self.service.validated_writes.clear()
            return True

        with patch.object(self.adapter, "_authorized", side_effect=revoke):
            self.assertFalse(self.invoke("performance.cpu_boost", "true").success)
        self.platform.set_cpu_boost.assert_not_called()

    def test_backend_failure_and_dbus_errors_propagate(self):
        self.service.validated_writes = {"performance.cpu_boost"}
        self.platform.set_cpu_boost.side_effect = lambda value: OperationResult(
            False, "performance.cpu_boost", value, error_message="Read-back mismatch",
        )
        self.assertIn("Read-back mismatch", self.client.set_capability("performance.cpu_boost", True).error_message)
        self.bus.error = GLib.Error("daemon vanished")
        self.assertFalse(self.client.set_capability("performance.cpu_boost", True).success)

    def test_client_rejects_nonfinite_json_without_calling_bus(self):
        for value in (float("nan"), float("inf")):
            self.assertFalse(self.client.set_capability("cooling.internal_fan", value).success)
        self.assertEqual(self.bus.calls, [])

    def test_unexpected_backend_error_is_generic(self):
        self.service.get_capability_snapshot.side_effect = RuntimeError("secret root path")
        invocation = FakeInvocation()
        self.adapter.handle_method_call(self.bus, ":1.42", OBJECT_PATH, INTERFACE, "GetSnapshot", None, invocation)
        self.assertEqual(invocation.error, (f"{INTERFACE}.Error.Failed", "Service operation failed."))

    def test_system_service_excludes_owner_authorization_and_session_bus(self):
        service = system_service()
        self.assertEqual(service.validated_writes, set())
        self.assertEqual(service.platform.authorized_writes, set())
        self.assertIsNone(service.brightness_owner.read())
        for cid, value in (("performance.epp", "balanced"), ("display.brightness", 50)):
            self.assertFalse(service.set_capability(cid, value).success)
        self.assertEqual(LOCALLY_VALIDATED_WRITES, OWNER_ROUTED_WRITES)

    def test_selection_falls_back_when_name_absent_or_bus_unavailable(self):
        self.bus.owned = False
        with patch.object(Gio, "bus_get_sync", return_value=self.bus) as get_bus:
            self.assertIsInstance(select_client(), LocalServiceClient)
        get_bus.assert_called_once_with(Gio.BusType.SYSTEM, None)
        with patch.object(Gio, "bus_get_sync", side_effect=GLib.Error("no system bus")):
            self.assertIsInstance(select_client(), LocalServiceClient)

    def test_selection_uses_dbus_router_when_name_owned(self):
        with patch.object(Gio, "bus_get_sync", return_value=self.bus):
            selected = select_client()
        self.assertIsInstance(selected, SessionServiceClient)
        self.assertIsInstance(selected.system, DBusServiceClient)
        self.assertEqual(self.bus.calls[-1][3], "NameHasOwner")

    def test_router_preserves_system_records_and_overlays_session_records(self):
        remote = Mock()
        local = Mock()
        remote_record = snapshot().capabilities[0]
        owner_records = [CapabilityRecord(cid, cid, CapabilityStatus.CONFIRMED_LOCAL,
                                         read_supported=True, write_supported=True,
                                         write_authorized=True, locally_validated=True)
                         for cid in OWNER_ROUTED_WRITES]
        remote.get_snapshot.return_value = CapabilitySnapshot(1, "remote", [remote_record] + [
            replace(record, write_authorized=False, observed_value="system") for record in owner_records
        ])
        local.get_snapshot.return_value = CapabilitySnapshot(1, "local", [
            replace(remote_record, observed_value="ignore local platform record"), *owner_records,
        ])
        router = SessionServiceClient(remote, local)
        merged = router.get_snapshot()
        self.assertIs(merged.capabilities[0], remote_record)
        for owner_record in owner_records:
            self.assertIs(merged.by_id(owner_record.capability_id), owner_record)
        for cid in OWNER_ROUTED_WRITES:
            router.set_capability(cid, 50)
        self.assertEqual(local.set_capability.call_count, 2)
        remote.set_capability.assert_not_called()
        router.set_capability("performance.cpu_boost", True)
        remote.set_capability.assert_called_once_with("performance.cpu_boost", True)
        remote.get_snapshot.side_effect = GLib.Error("daemon vanished")
        with self.assertRaises(GLib.Error):
            router.get_snapshot()
        self.assertEqual(local.get_snapshot.call_count, 1)


class AsyncApplyTests(unittest.TestCase):
    def setUp(self):
        guard = patch.object(Gio, "bus_get_sync", side_effect=AssertionError("real bus"))
        guard.start()
        self.addCleanup(guard.stop)

    def deliver(self, received):
        context = GLib.MainContext.default()
        deadline = time.monotonic() + 2
        while not received and time.monotonic() < deadline:
            context.iteration(False)
            time.sleep(0.001)
        self.assertTrue(received, "main-loop result delivery did not run")

    def test_async_client_runs_apply_and_readback_off_thread_delivers_on_main_loop(self):
        main_thread = threading.get_ident()
        calls = []
        client = Mock()

        def apply(cid, value):
            calls.append(("set", threading.get_ident()))
            return OperationResult(True, cid, value, observed_value=value)

        def read():
            calls.append(("read", threading.get_ident()))
            return snapshot(True)

        client.set_capability.side_effect = apply
        client.get_snapshot.side_effect = read
        received = []
        future = apply_capability_async(client, "performance.cpu_boost", True,
                                        lambda result, state: received.append((result, state, threading.get_ident())))
        future.result(timeout=2)
        self.assertEqual(received, [])  # completion is queued, not invoked by worker
        self.deliver(received)
        self.assertEqual([call[0] for call in calls], ["set", "read"])
        self.assertTrue(all(call[1] != main_thread for call in calls))
        self.assertTrue(received[0][0].success)
        self.assertTrue(received[0][1].capabilities[0].observed_value)
        self.assertEqual(received[0][2], main_thread)

    def test_async_requests_are_serialized_with_readback(self):
        calls = []
        client = Mock()
        client.set_capability.side_effect = lambda cid, value: (
            calls.append(value), OperationResult(True, cid, value)
        )[1]
        client.get_snapshot.side_effect = lambda: (calls.append("read"), snapshot())[1]
        received = []
        futures = [apply_capability_async(client, "performance.cpu_boost", value,
                                          lambda *args: received.append(args)) for value in (True, False)]
        for future in futures:
            future.result(timeout=2)
        self.deliver(received)
        self.assertEqual(calls, [True, "read", False, "read"])
        # Drain the second queued callback before the next test.
        deadline = time.monotonic() + 2
        while len(received) < 2 and time.monotonic() < deadline:
            GLib.MainContext.default().iteration(False)
        self.assertEqual(len(received), 2)

    def test_async_failure_still_fetches_observed_state(self):
        for raises in (False, True):
            client = Mock()
            client.set_capability.return_value = OperationResult(False, "performance.cpu_boost", error_message="denied")
            if raises:
                client.set_capability.side_effect = RuntimeError("owner vanished")
            client.get_snapshot.return_value = snapshot()
            received = []
            apply_capability_async(client, "performance.cpu_boost", True,
                                   lambda *args: received.append(args)).result(timeout=2)
            self.deliver(received)
            self.assertFalse(received[0][0].success)
            self.assertIs(received[0][1], client.get_snapshot.return_value)

    def test_async_snapshot_failure_is_reported_on_main_loop(self):
        client = Mock()
        client.set_capability.return_value = OperationResult(True, "performance.cpu_boost")
        client.get_snapshot.side_effect = GLib.Error("daemon gone")
        received = []
        apply_capability_async(client, "performance.cpu_boost", True,
                               lambda *args: received.append(args)).result(timeout=2)
        self.deliver(received)
        self.assertFalse(received[0][0].success)
        self.assertIn("Refresh failed", received[0][0].error_message)
        self.assertIsNone(received[0][1])

    def test_window_returns_while_write_is_blocked_then_renders_readback(self):
        entered, release = threading.Event(), threading.Event()
        client = Mock()

        def blocked_set(cid, value):
            entered.set()
            if not release.wait(2):
                raise RuntimeError("test did not release worker")
            return OperationResult(True, cid, value)

        client.set_capability.side_effect = blocked_set
        client.get_snapshot.return_value = snapshot(True)
        page = Mock()
        window = SimpleNamespace(client=client, pages={"performance": page})
        from superx_helper.client import apply_capability_async as real_apply
        with patch("superx_helper.ui.window.apply_capability_async", wraps=real_apply) as apply_async:
            try:
                SuperXWindow._apply_capability(window, "performance.cpu_boost", True)
                self.assertTrue(entered.wait(1))
                page.update_from_snapshot.assert_not_called()
            finally:
                release.set()
        self.deliver(page.update_from_snapshot.call_args_list)
        page.update_from_snapshot.assert_called_once_with(client.get_snapshot.return_value)
        apply_async.assert_called_once()

    def test_window_toasts_failure_on_main_loop_and_renders_observed_state(self):
        client = Mock()
        client.set_capability.return_value = OperationResult(
            False, "performance.cpu_boost", error_message="Write rejected",
        )
        client.get_snapshot.return_value = snapshot(False)
        page, overlay = Mock(), Mock()
        window = SimpleNamespace(client=client, pages={"performance": page}, _toast_overlay=lambda: overlay)
        with patch("superx_helper.ui.window.Adw.Toast.new", return_value="toast") as toast:
            SuperXWindow._apply_capability(window, "performance.cpu_boost", True)
            self.deliver(page.update_from_snapshot.call_args_list)
        toast.assert_called_once_with("Write rejected")
        overlay.add_toast.assert_called_once_with("toast")
        page.update_from_snapshot.assert_called_once_with(client.get_snapshot.return_value)


class DeploymentPolicyTests(unittest.TestCase):
    def test_polkit_actions_match_fixed_map_and_require_admin(self):
        root = Path(__file__).resolve().parents[1]
        policy = ET.parse(root / "contrib/polkit/org.sonoran.SuperXHelper.policy").getroot()
        self.assertEqual({action.attrib["id"] for action in policy.findall("action")}, set(CAPABILITY_ACTIONS.values()))
        for action in policy.findall("action"):
            self.assertEqual(action.findtext("defaults/allow_active"), "auth_admin_keep")
            self.assertEqual(action.findtext("defaults/allow_inactive"), "no")
            self.assertEqual(action.findtext("defaults/allow_any"), "no")

    def test_bus_policy_limits_name_owner_and_console_methods(self):
        root = Path(__file__).resolve().parents[1]
        policy = ET.parse(root / "contrib/dbus/org.sonoran.SuperXHelper1.conf").getroot()
        self.assertEqual(policy.find("policy[@user='root']/allow").attrib, {"own": BUS_NAME})
        self.assertIsNotNone(policy.find("policy[@context='default']/deny[@own]"))
        allows = policy.findall("policy[@at_console='true']/allow")
        self.assertEqual({item.attrib["send_member"] for item in allows}, {"GetSnapshot", "SetCapability"})
        for item in allows:
            self.assertEqual(item.attrib["send_destination"], BUS_NAME)
            self.assertEqual(item.attrib["send_interface"], INTERFACE)
            self.assertEqual(item.attrib["send_path"], OBJECT_PATH)


if __name__ == "__main__":
    unittest.main()
