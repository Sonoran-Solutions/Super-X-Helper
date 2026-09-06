"""Storage diagnostics and Mini SSD reliability page."""

from __future__ import annotations

from typing import Optional

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

from superx_helper.contracts import CapabilityId, CapabilitySnapshot
from superx_helper.ui.pages.base import BasePage
from superx_helper.ui.widgets import MiniSsdStatusCard
from superx_helper.ui_manifest import PageSpec


class StoragePage(BasePage):
    """Storage diagnostics and reliability page."""

    def __init__(self, spec: Optional[PageSpec] = None):
        super().__init__(
            spec
            or PageSpec(
                "storage",
                "Storage",
                [
                    CapabilityId.MINI_SSD_PRESENCE.value,
                    CapabilityId.MINI_SSD_RELIABILITY.value,
                ],
            )
        )
        self.mini_card_group = Adw.PreferencesGroup()
        self.mini_card_group.set_title("Removable Storage Subsystem")
        self.add(self.mini_card_group)

    def update_from_snapshot(self, snapshot: CapabilitySnapshot) -> None:
        super().update_from_snapshot(snapshot)

        self.remove(self.mini_card_group)
        self.mini_card_group = Adw.PreferencesGroup()
        self.mini_card_group.set_title("Removable Storage Subsystem")

        presence = snapshot.by_id(CapabilityId.MINI_SSD_PRESENCE.value)
        reliability = snapshot.by_id(CapabilityId.MINI_SSD_RELIABILITY.value)
        self.mini_card_group.add(MiniSsdStatusCard(presence, reliability))
        self.add(self.mini_card_group)
