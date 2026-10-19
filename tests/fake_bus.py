"""Shared fake D-Bus connection for owner tests (never touches a real bus)."""

from gi.repository import GLib


class FakeBus:
    """Return real Variants without connecting to D-Bus."""

    def __init__(self):
        self.values = {
            "ActiveProfile": GLib.Variant("s", "balanced"),
            "Profiles": GLib.Variant("aa{sv}", [
                {"Profile": GLib.Variant("s", profile)}
                for profile in ("power-saver", "balanced", "performance")
            ]),
            "PerformanceDegraded": GLib.Variant("s", ""),
            "PerformanceInhibited": GLib.Variant("s", ""),
            "ActiveProfileHolds": GLib.Variant("aa{sv}", []),
            "Brightness": GLib.Variant("i", 50),
        }
        self.calls = []
        self.error = None
        self.error_method = None
        self.apply_set = True
        self.brightness_reads = []

    def call_sync(self, name, path, iface, method, params, reply_type, flags, timeout, cancellable):
        self.calls.append((name, path, iface, method, params, timeout))
        if self.error and (self.error_method is None or self.error_method == method):
            raise self.error
        if iface != "org.freedesktop.DBus.Properties" or timeout != 2000:
            raise AssertionError("Expected bounded property access")
        prop = params.unpack()[1]
        if method == "Get":
            value = self.values[prop]
            if prop == "Brightness" and self.brightness_reads:
                value = GLib.Variant("i", self.brightness_reads.pop(0))
            return GLib.Variant("(v)", (value,))
        if method == "Set":
            if self.apply_set:
                self.values[prop] = params.get_child_value(2).get_variant()
            return GLib.Variant("()", ())
        raise AssertionError(method)

    def sets(self):
        return [call for call in self.calls if call[3] == "Set"]
