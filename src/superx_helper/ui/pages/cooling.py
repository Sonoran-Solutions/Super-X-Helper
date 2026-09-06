"""Cooling management page for internal fans and Frost Bay dock."""

from __future__ import annotations

from typing import Optional

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

from superx_helper.contracts import CapabilityId, CapabilitySnapshot
from superx_helper.ui.pages.base import BasePage
from superx_helper.ui.widgets import CapabilityRow, FrostBayResearchCard
from superx_helper.ui_manifest import PageSpec


class CoolingPage(BasePage):
    """Cooling management page."""

    def __init__(self, spec: Optional[PageSpec] = None):
        super().__init__(
            spec
            or PageSpec(
                "cooling",
                "Cooling",
                [
                    CapabilityId.INTERNAL_FAN.value,
                    CapabilityId.FROST_BAY_TELEMETRY.value,
                    CapabilityId.FROST_BAY_CONTROL.value,
                ],
            )
        )
        self.fb_group = Adw.PreferencesGroup()
        self.fb_group.set_title("External Liquid Cooling Dock")
        self.add(self.fb_group)

    def update_from_snapshot(self, snapshot: CapabilitySnapshot) -> None:
        super().update_from_snapshot(snapshot)

        self.remove(self.fb_group)
        self.fb_group = Adw.PreferencesGroup()
        self.fb_group.set_title("External Liquid Cooling Dock")
        fb_rec = snapshot.by_id(CapabilityId.FROST_BAY_TELEMETRY.value)
        self.fb_group.add(FrostBayResearchCard(fb_rec))
        self.add(self.fb_group)
