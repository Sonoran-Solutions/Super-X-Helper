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
            "Pre-Astra profile management is read-only. Dynamic switching requires privileged daemon authorization."
        )

        profiles_data = [
            ("Quiet", "Low power envelope (15W - 28W) • Silent fan curve", False),
            ("Balanced", "Default balanced envelope (35W - 45W) • Automatic fan curve", True),
            ("Performance", "Maximum air-cooled envelope (54W - 65W) • Aggressive fan curve", False),
            ("Liquid Turbo", "120W envelope • Reserved for validated Frost Bay dock (Blocked)", False),
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
