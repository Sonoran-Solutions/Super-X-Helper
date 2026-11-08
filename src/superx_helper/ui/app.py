"""GTK4 / Libadwaita Application entry point for Super X Helper."""

from __future__ import annotations

import argparse
import sys
from typing import Optional

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib

from superx_helper.client import DBusServiceClient, LocalServiceClient, ServiceClient, SessionServiceClient
from superx_helper.dbus_service import BUS_NAME
from superx_helper.service import SuperXService
from superx_helper.ui.window import SuperXWindow


def select_client() -> ServiceClient:
    local = LocalServiceClient(SuperXService())
    try:
        connection = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        owned = connection.call_sync(
            "org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus",
            "NameHasOwner", GLib.Variant("(s)", (BUS_NAME,)),
            GLib.VariantType.new("(b)"), Gio.DBusCallFlags.NO_AUTO_START, 2000, None,
        ).unpack()[0]
        if owned:
            return SessionServiceClient(DBusServiceClient(connection), local)
    except GLib.Error:
        pass
    return local


class SuperXApplication(Adw.Application):
    """Primary Libadwaita desktop application."""

    def __init__(self, client: Optional[ServiceClient] = None):
        super().__init__(
            application_id="org.sonoran.SuperXHelper",
            flags=Gio.ApplicationFlags.FLAGS_NONE,
        )
        self.client = client
        self.window: Optional[SuperXWindow] = None

    def do_activate(self) -> None:
        if not self.window:
            if self.client is None:
                self.client = select_client()

            self.window = SuperXWindow(self, self.client)

        self.window.present()


def main(args: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Super X Helper - Linux Control Center")
    parser.add_argument(
        "--test-run",
        action="store_true",
        help="Initialize the application shell, verify page creation and snapshot update, and exit.",
    )
    parsed, remaining = parser.parse_known_args(args or sys.argv[1:])

    app = SuperXApplication()

    if parsed.test_run:
        Adw.init()
        app.register()
        service = SuperXService()
        client = LocalServiceClient(service)
        window = SuperXWindow(app, client)
        window.refresh()
        print(f"[✓] Application shell initialized with {len(window.pages)} pages.")
        return 0

    return app.run([sys.argv[0]] + remaining)


if __name__ == "__main__":
    sys.exit(main())
