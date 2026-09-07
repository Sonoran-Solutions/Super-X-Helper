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
            "Profiles exist as named placeholders only. No fan curve, wattage "
            "envelope, or other profile policy is claimed until the service "
            "contract defines it."
        )

        profiles_data = [
            ("Quiet", "Intent: prioritize lower fan noise. Fan/power policy not yet defined.", False),
            ("Balanced", "Intent: balanced default operation. Profile policy not yet defined.", False),
            ("Performance", "Intent: prioritize performance. Profile policy not yet defined.", False),
            ("Liquid Turbo", "Intent: higher performance with Frost Bay cooling. Blocked until Frost Bay qualification.", False),
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
