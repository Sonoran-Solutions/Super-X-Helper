"""Fresh D-Bus property access to the existing power and display owners."""

from __future__ import annotations

import time
from typing import Any, Optional

from gi.repository import Gio, GLib

from superx_helper.contracts import CapabilityId, OperationResult


def _get_prop(bus: Gio.DBusConnection, name: str, path: str, iface: str, prop: str) -> Any:
    return bus.call_sync(
        name, path, "org.freedesktop.DBus.Properties", "Get",
        GLib.Variant("(ss)", (iface, prop)), GLib.VariantType.new("(v)"),
        Gio.DBusCallFlags.NONE, 2000, None,
    ).unpack()[0]


def _set_prop(bus: Gio.DBusConnection, name: str, path: str, iface: str,
              prop: str, value: GLib.Variant) -> None:
    bus.call_sync(
        name, path, "org.freedesktop.DBus.Properties", "Set",
        GLib.Variant("(ssv)", (iface, prop, value)), GLib.VariantType.new("()"),
        Gio.DBusCallFlags.NONE, 2000, None,
    )


class PowerProfilesOwner:
    """Use power-profiles-daemon instead of competing with its EPP policy."""

    name = "net.hadess.PowerProfiles"
    path = "/net/hadess/PowerProfiles"
    iface = "net.hadess.PowerProfiles"

    def __init__(self, bus: Optional[Gio.DBusConnection] = None):
        self.bus = bus

    def _bus(self) -> Gio.DBusConnection:
        if self.bus is None:
            self.bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        return self.bus

    def read(self) -> Optional[str]:
        try:
            return _get_prop(self._bus(), self.name, self.path, self.iface, "ActiveProfile")
        except GLib.Error:
            return None

    def profiles(self) -> list[str]:
        try:
            profiles = _get_prop(self._bus(), self.name, self.path, self.iface, "Profiles")
            return [item["Profile"] for item in profiles if isinstance(item.get("Profile"), str)]
        except GLib.Error:
            return []

    def status(self) -> dict[str, Any]:
        try:
            return {
                prop: _get_prop(self._bus(), self.name, self.path, self.iface, prop)
                for prop in ("PerformanceDegraded", "PerformanceInhibited", "ActiveProfileHolds")
            }
        except GLib.Error:
            return {}

    def set(self, value: Any) -> OperationResult:
        result = OperationResult(False, CapabilityId.CPU_EPP.value, value)
        if not isinstance(value, str) or value not in self.profiles():
            result.error_message = "Power profile must be a string in the owner's available profiles (owner may be unavailable)."
            return result
        try:
            bus = self._bus()
            _set_prop(bus, self.name, self.path, self.iface, "ActiveProfile", GLib.Variant("s", value))
            result.observed_value = _get_prop(bus, self.name, self.path, self.iface, "ActiveProfile")
            result.success = result.observed_value == value
            if not result.success:
                result.error_message = f"Power profile read-back mismatch: requested {value!r}, observed {result.observed_value!r}."
        except GLib.Error as error:
            result.error_message = f"Power profile operation failed: {error}"
        return result


class GsdBrightnessOwner:
    """Control session brightness with a floor that keeps the panel visible."""

    name = "org.gnome.SettingsDaemon.Power"
    path = "/org/gnome/SettingsDaemon/Power"
    iface = "org.gnome.SettingsDaemon.Power.Screen"

    def __init__(self, bus: Optional[Gio.DBusConnection] = None):
        self.bus = bus

    def _bus(self) -> Gio.DBusConnection:
        if self.bus is None:
            self.bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        return self.bus

    def read(self) -> Optional[int]:
        try:
            return _get_prop(self._bus(), self.name, self.path, self.iface, "Brightness")
        except GLib.Error:
            return None

    def set(self, value: Any) -> OperationResult:
        result = OperationResult(False, CapabilityId.DISPLAY_BRIGHTNESS.value, value)
        if (isinstance(value, bool) or not isinstance(value, (int, float))
                or not 5 <= value <= 100 or int(value) != value):
            result.error_message = "Brightness expects an integer numeric percentage in [5, 100]."
            return result
        try:
            bus = self._bus()
            current = _get_prop(bus, self.name, self.path, self.iface, "Brightness")
            if current == -1:
                result.observed_value = current
                result.error_message = "Session brightness owner has no backlight."
                return result
            _set_prop(bus, self.name, self.path, self.iface, "Brightness", GLib.Variant("i", int(value)))
            for attempt in range(11):
                if attempt:
                    time.sleep(0.1)
                result.observed_value = _get_prop(bus, self.name, self.path, self.iface, "Brightness")
                if result.observed_value == value:
                    result.success = True
                    return result
            result.error_message = f"Brightness read-back mismatch: requested {value!r}, observed {result.observed_value!r}."
        except GLib.Error as error:
            result.error_message = f"Session brightness operation failed: {error}"
        return result
