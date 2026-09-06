"""GTK4 / Libadwaita Application entry point for Super X Helper."""

from __future__ import annotations

import argparse
import sys
from typing import Optional

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib

from superx_helper.client import LocalServiceClient, ServiceClient
from superx_helper.service import SuperXService
from superx_helper.ui.window import SuperXWindow


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
                service = SuperXService()
                self.client = LocalServiceClient(service)

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
