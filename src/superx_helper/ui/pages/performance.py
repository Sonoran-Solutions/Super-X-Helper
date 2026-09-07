"""Performance controls page."""

from __future__ import annotations

from typing import Optional

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

from superx_helper.contracts import CapabilityId, CapabilitySnapshot
from superx_helper.ui.pages.base import BasePage
from superx_helper.ui.widgets import CapabilityRow, SafetyBanner
from superx_helper.ui_manifest import PageSpec


class PerformancePage(BasePage):
    """Performance page managing CPU scaling, TDP, and boost toggles."""

    def __init__(self, spec: Optional[PageSpec] = None):
        super().__init__(
            spec
            or PageSpec(
                "performance",
                "Performance",
                [
                    CapabilityId.CPU_BOOST.value,
                    CapabilityId.CPU_EPP.value,
                    CapabilityId.POWER_TARGET.value,
                ],
            )
        )

        self.liquid_group = Adw.PreferencesGroup()
        self.liquid_group.set_title("Liquid-Cooled High Power Envelope")
        liquid_row = Adw.ActionRow()
        liquid_row.set_title("Liquid Turbo Envelope")
        liquid_row.set_subtitle(
            "Unavailable • Blocked pending Frost Bay protocol and safety qualification"
        )
        liquid_row.set_sensitive(False)
        self.liquid_group.add(liquid_row)
        self.add(self.liquid_group)
