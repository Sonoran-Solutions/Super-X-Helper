"""Profiles management page skeleton."""

from __future__ import annotations

from typing import Optional

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

from superx_helper.contracts import CapabilitySnapshot
from superx_helper.ui.pages.base import BasePage
from superx_helper.ui_manifest import PageSpec


class ProfilesPage(BasePage):
    """Profiles management page."""

    def __init__(self, spec: Optional[PageSpec] = None):
        super().__init__(spec or PageSpec("profiles", "Profiles", []))

        self.profiles_group = Adw.PreferencesGroup()
        self.profiles_group.set_title("Available Hardware Profiles")
        self.profiles_group.set_description(
            "Profiles exist as named placeholders. No profile state or wattage envelope is claimed without backend service support."
        )

        profiles_data = [
            ("Quiet", "Low noise priority preset • Reduced fan curve", False),
            ("Balanced", "Standard operating envelope placeholder • Automatic fan curve", False),
            ("Performance", "High performance profile placeholder • Aggressive fan curve", False),
            ("Liquid Turbo", "External liquid-cooling profile placeholder • Blocked pending Frost Bay qualification", False),
        ]

        for name, desc, is_active in profiles_data:
            row = Adw.ActionRow()
            row.set_title(name)
            row.set_subtitle(desc)

            radio = Gtk.CheckButton()
            radio.set_active(is_active)
            radio.set_sensitive(False)  # Disabled in read-only phase
            row.add_suffix(radio)
            self.profiles_group.add(row)

        self.add(self.profiles_group)

    def update_from_snapshot(self, snapshot: CapabilitySnapshot) -> None:
        pass
