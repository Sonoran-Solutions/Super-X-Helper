"""Service clients and serialized background apply/read-back for GTK callers."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Optional, Protocol

from gi.repository import Gio, GLib

from superx_helper.contracts import CapabilitySnapshot, OperationResult
from superx_helper.service import SuperXService
from superx_helper.dbus_service import BUS_NAME, INTERFACE, OBJECT_PATH, POLKIT_TIMEOUT_MS
from superx_helper.policy import OWNER_ROUTED_WRITES
from superx_helper.transport import operation_result_from_dict, snapshot_from_dict


class ServiceClient(Protocol):
    """Frontend-facing service surface.

    Both the in-process development client and the future D-Bus client
    implement this.  ``set_capability`` is typed and capability-scoped; it never
    exposes raw sysfs paths or shell strings.
    """

    def get_snapshot(self) -> CapabilitySnapshot:
        ...

    def set_capability(self, capability_id: str, value: Any) -> OperationResult:
        ...


class LocalServiceClient:
    mode = "Local session"

    def __init__(self, service: SuperXService):
        self.service = service

    def get_snapshot(self) -> CapabilitySnapshot:
        return self.service.get_capability_snapshot()

    def set_capability(self, capability_id: str, value: Any) -> OperationResult:
        return self.service.set_capability(capability_id, value)


class DBusServiceClient:
    mode = "System D-Bus"

    def __init__(self, connection: Gio.DBusConnection):
        self.connection = connection

    def _call(self, method, parameters, timeout=5000):
        reply = self.connection.call_sync(
            BUS_NAME, OBJECT_PATH, INTERFACE, method, parameters,
            GLib.VariantType.new("(s)"), Gio.DBusCallFlags.NO_AUTO_START,
            timeout, None,
        )
        return json.loads(reply.unpack()[0])

    def get_snapshot(self) -> CapabilitySnapshot:
        return snapshot_from_dict(self._call("GetSnapshot", None))

    def set_capability(self, capability_id: str, value: Any) -> OperationResult:
        try:
            return operation_result_from_dict(self._call(
                "SetCapability", GLib.Variant("(ss)", (
                    capability_id, json.dumps(value, allow_nan=False),
                )), POLKIT_TIMEOUT_MS + 5000,
            ))
        except (GLib.Error, ValueError, TypeError, KeyError) as error:
            return OperationResult(False, capability_id, value, error_message=f"D-Bus write failed: {error}")


class SessionServiceClient:
    """Overlay desktop-owner records; never send owner writes to root."""

    mode = "System D-Bus + session owners"

    def __init__(self, system: DBusServiceClient, local: LocalServiceClient):
        self.system = system
        self.local = local

    def get_snapshot(self) -> CapabilitySnapshot:
        snapshot = self.system.get_snapshot()
        owners = {record.capability_id: record for record in self.local.get_snapshot().capabilities
                  if record.capability_id in OWNER_ROUTED_WRITES}
        return CapabilitySnapshot(snapshot.schema_version, snapshot.generated_at, [
            owners.get(record.capability_id, record) for record in snapshot.capabilities
        ])

    def set_capability(self, capability_id: str, value: Any) -> OperationResult:
        client = self.local if capability_id in OWNER_ROUTED_WRITES else self.system
        return client.set_capability(capability_id, value)


# One worker preserves request/read-back order, including the brightness poll.
_apply_worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix="superx-apply")


def apply_capability_async(
    client: ServiceClient, capability_id: str, value: Any,
    callback: Callable[[OperationResult, Optional[CapabilitySnapshot]], None],
):
    """Apply and fetch read-back off-thread; deliver only on GLib's main loop."""
    def work():
        try:
            result = client.set_capability(capability_id, value)
        except Exception as error:
            result = OperationResult(False, capability_id, value, error_message=f"Write failed: {error}")
        snapshot = None
        try:
            snapshot = client.get_snapshot()
        except Exception as error:
            result.success = False
            result.error_message = (result.error_message or "State may have changed.") + f" Refresh failed: {error}"

        def deliver():
            callback(result, snapshot)
            return GLib.SOURCE_REMOVE

        GLib.idle_add(deliver)

    return _apply_worker.submit(work)
