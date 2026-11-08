"""Narrow system-bus boundary; desktop-owned controls stay in the session."""

from __future__ import annotations

import json
import math
import signal

from gi.repository import Gio, GLib

from superx_helper.dbus_names import BUS_NAME, OBJECT_PATH, INTERFACE, POLKIT_TIMEOUT_MS
from superx_helper.contracts import CapabilityId, OperationResult
from superx_helper.policy import LOCALLY_VALIDATED_WRITES, OWNER_ROUTED_WRITES
from superx_helper.service import SuperXService, coerce_capability_id
from superx_helper.transport import operation_result_to_dict, snapshot_to_dict

MAX_VALUE_BYTES = 4096

# Exact ids only: no prefix matching or caller-provided action names.
CAPABILITY_ACTIONS = {
    CapabilityId.CPU_BOOST.value: "org.sonoran.SuperXHelper.set-performance",
    CapabilityId.INTERNAL_FAN.value: "org.sonoran.SuperXHelper.set-cooling",
}

INTROSPECTION_XML = f"""<node>
  <interface name="{INTERFACE}">
    <method name="GetSnapshot">
      <arg name="snapshot_json" type="s" direction="out"/>
    </method>
    <method name="SetCapability">
      <arg name="capability_id" type="s" direction="in"/>
      <arg name="value_json" type="s" direction="in"/>
      <arg name="result_json" type="s" direction="out"/>
    </method>
  </interface>
</node>"""


def decode_value(capability_id: str, value_json: str):
    """Bound and type-check untrusted JSON before authorization or dispatch."""
    if len(value_json.encode("utf-8")) > MAX_VALUE_BYTES:
        raise ValueError("Value JSON exceeds 4096 bytes.")

    def reject_constant(value):
        raise ValueError("Non-finite numbers are not allowed.")

    value = json.loads(value_json, parse_constant=reject_constant)
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("Non-finite numbers are not allowed.")
    if capability_id == CapabilityId.CPU_BOOST.value:
        valid = type(value) is bool
    elif capability_id == CapabilityId.INTERNAL_FAN.value:
        valid = type(value) is int and 0 <= value <= 100
    else:
        valid = False
    if not valid:
        raise ValueError("Value has the wrong type or range for this capability.")
    return value


class _NoSessionBrightness:
    """Do not resolve a session bus (including root's) from the system daemon."""

    def read(self):
        return None


def system_service() -> SuperXService:
    return SuperXService(
        validated_writes=LOCALLY_VALIDATED_WRITES - OWNER_ROUTED_WRITES,
        brightness_owner=_NoSessionBrightness(),
    )


class DBusService:
    def __init__(self, service: SuperXService):
        self.service = service

    def register(self, connection: Gio.DBusConnection) -> int:
        info = Gio.DBusNodeInfo.new_for_xml(INTROSPECTION_XML)
        return connection.register_object(
            OBJECT_PATH, info.interfaces[0], self.handle_method_call, None, None,
        )

    def _authorized(self, connection, sender: str, action: str, callback):
        # sender is supplied by the bus, never by the JSON request. Use the
        # system-bus-name subject so polkit resolves the caller's credentials.
        connection.call(
            "org.freedesktop.PolicyKit1", "/org/freedesktop/PolicyKit1/Authority",
            "org.freedesktop.PolicyKit1.Authority", "CheckAuthorization",
            GLib.Variant("((sa{sv})sa{ss}us)", (
                ("system-bus-name", {"name": GLib.Variant("s", sender)}),
                action, {}, 1, "",
            )),
            GLib.VariantType.new("((bba{ss}))"), Gio.DBusCallFlags.NONE,
            POLKIT_TIMEOUT_MS, None, callback, None,
        )

    def set_capability(self, connection, sender, capability_id, value_json, complete, failed):
        cid = coerce_capability_id(capability_id)
        if cid is None:
            return OperationResult(False, capability_id, error_message="Unknown capability id.")
        if capability_id not in CAPABILITY_ACTIONS:
            return OperationResult(False, capability_id, error_message=(
                "Capability has no privileged write policy. This capability must use its desktop owner in the user's session."
                if capability_id in OWNER_ROUTED_WRITES else "Capability has no privileged write policy."
            ))
        try:
            value = decode_value(capability_id, value_json)
        except (ValueError, RecursionError) as error:
            return OperationResult(False, capability_id, error_message=f"Invalid value JSON: {error}")
        if capability_id in OWNER_ROUTED_WRITES:
            return OperationResult(False, capability_id, value, error_message="This capability must use its desktop owner in the user's session.")
        # The facade is the authorization authority. Avoid prompting for writes
        # it already forbids, and check it again after polkit before dispatch.
        if capability_id not in self.service.validated_writes:
            return self.service.set_capability(capability_id, value)

        def authorized(source, result, user_data):
            try:
                try:
                    allowed = source.call_finish(result).unpack()[0][0]
                except GLib.Error:
                    allowed = False
                if not allowed:
                    complete(OperationResult(False, capability_id, value, error_message="Polkit authorization denied or unavailable."))
                else:
                    # Recheck facade authorization after the asynchronous prompt.
                    complete(self.service.set_capability(capability_id, value))
            except Exception:
                failed()

        self._authorized(connection, sender, CAPABILITY_ACTIONS[capability_id], authorized)
        return None

    def handle_method_call(self, connection, sender, path, interface, method, parameters, invocation):
        def failed():
            # Do not expose backend paths or root-process exception details.
            invocation.return_dbus_error(f"{INTERFACE}.Error.Failed", "Service operation failed.")

        def complete(result):
            try:
                data = operation_result_to_dict(result)
                invocation.return_value(GLib.Variant("(s)", (json.dumps(data, allow_nan=False),)))
            except Exception:
                failed()

        try:
            if method == "GetSnapshot":
                data = snapshot_to_dict(self.service.get_capability_snapshot())
                invocation.return_value(GLib.Variant("(s)", (json.dumps(data, allow_nan=False),)))
            elif method == "SetCapability":
                result = self.set_capability(connection, sender, *parameters.unpack(), complete, failed)
                if result is not None:
                    complete(result)
            else:
                invocation.return_dbus_error("org.freedesktop.DBus.Error.UnknownMethod", "Unknown method.")
        except Exception:
            failed()


def main() -> int:
    loop = GLib.MainLoop()
    adapter = DBusService(system_service())
    registered = []
    status = 0

    def bus_acquired(connection, name):
        nonlocal status
        try:
            registered.append((connection, adapter.register(connection)))
        except Exception:
            status = 1
            loop.quit()

    def name_lost(connection, name):
        nonlocal status
        status = 1
        loop.quit()

    def stop():
        loop.quit()
        return GLib.SOURCE_REMOVE

    owner = Gio.bus_own_name(
        Gio.BusType.SYSTEM, BUS_NAME, Gio.BusNameOwnerFlags.NONE,
        bus_acquired, None, name_lost,
    )
    signals = [GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signum, stop)
               for signum in (signal.SIGTERM, signal.SIGINT)]
    try:
        loop.run()
    finally:
        for source in signals:
            if GLib.MainContext.default().find_source_by_id(source):
                GLib.source_remove(source)
        for connection, registration in registered:
            connection.unregister_object(registration)
        Gio.bus_unown_name(owner)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
