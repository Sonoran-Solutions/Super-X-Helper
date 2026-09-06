"""Base page implementation using Adw.PreferencesPage."""

from __future__ import annotations

from typing import Dict, List, Optional

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

from superx_helper.contracts import CapabilitySnapshot
from superx_helper.ui.widgets import CapabilityRow, SafetyBanner
from superx_helper.ui_manifest import PageSpec


class BasePage(Adw.PreferencesPage):
    """Generic capability-driven page built from a PageSpec."""

    def __init__(self, spec: PageSpec):
        super().__init__()
        self.spec = spec
        self.set_title(spec.title)

        # Container for dynamic content
        self.group = Adw.PreferencesGroup()
        self.group.set_title(spec.title)
        self.add(self.group)

        self.warnings_group = Adw.PreferencesGroup()
        self.add(self.warnings_group)

    def update_from_snapshot(self, snapshot: CapabilitySnapshot) -> None:
        """Rebuild rows based on latest capability snapshot."""
        # Clear existing rows in group
        self.remove(self.group)
        self.group = Adw.PreferencesGroup()
        self.group.set_title(self.spec.title)
        self.add(self.group)

        # Clear warnings
        self.remove(self.warnings_group)
        self.warnings_group = Adw.PreferencesGroup()
        self.add(self.warnings_group)

        page_caps = [
            snapshot.by_id(cap_id)
            for cap_id in self.spec.capability_ids
            if snapshot.by_id(cap_id) is not None
        ]

        # Populate rows
        for record in page_caps:
            row = CapabilityRow(record)
            self.group.add(row)

            # Display any specific warnings
            for warn in record.warnings:
                self.warnings_group.add(SafetyBanner(warn, record.safety_state))
