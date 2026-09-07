"""Dashboard page displaying system overview, active profile, and key cards."""

from __future__ import annotations

from typing import Optional

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

from superx_helper.contracts import CapabilityId, CapabilitySnapshot
from superx_helper.ui.widgets import (
    CapabilityRow,
    FrostBayResearchCard,
    MiniSsdStatusCard,
    SafetyBanner,
)
from superx_helper.ui_manifest import PageSpec


class DashboardPage(Adw.PreferencesPage):
    """Primary system overview dashboard."""

    def __init__(self, spec: Optional[PageSpec] = None):
        super().__init__()
        self.spec = spec or PageSpec("dashboard", "Dashboard", [])
        self.set_title("Dashboard")

        # System Performance Profile placeholder group
        self.profile_group = Adw.PreferencesGroup()
        self.profile_group.set_title("System Performance Profile")
        profile_row = Adw.ActionRow()
        profile_row.set_title("Active Profile")
        profile_row.set_subtitle("No active profile configured in service • Named placeholders only")
        self.profile_group.add(profile_row)
        self.add(self.profile_group)

        # Core Quick Status group
        self.status_group = Adw.PreferencesGroup()
        self.status_group.set_title("Platform Status")
        self.add(self.status_group)

        # Peripherals & External Hardware Cards group
        self.peripherals_group = Adw.PreferencesGroup()
        self.peripherals_group.set_title("Hardware and Subsystems")
        self.add(self.peripherals_group)

        # System Warnings group
        self.warnings_group = Adw.PreferencesGroup()
        self.add(self.warnings_group)

    def update_from_snapshot(self, snapshot: CapabilitySnapshot) -> None:
        # 1. Update Platform Status Group
        self.remove(self.status_group)
        self.status_group = Adw.PreferencesGroup()
        self.status_group.set_title("Platform Status")

        key_ids = [
            CapabilityId.CPU_BOOST.value,
            CapabilityId.CPU_EPP.value,
            CapabilityId.INTERNAL_FAN.value,
            CapabilityId.BATTERY_TELEMETRY.value,
            CapabilityId.DISPLAY_MODE.value,
        ]

        for cid in key_ids:
            rec = snapshot.by_id(cid)
            if rec:
                self.status_group.add(CapabilityRow(rec))
        self.add(self.status_group)

        # 2. Update Peripherals Group (Frost Bay and Mini SSD)
        self.remove(self.peripherals_group)
        self.peripherals_group = Adw.PreferencesGroup()
        self.peripherals_group.set_title("Hardware and Subsystems")

        # Frost Bay Card (renders RESEARCH_PENDING)
        fb_telemetry = snapshot.by_id(CapabilityId.FROST_BAY_TELEMETRY.value)
        self.peripherals_group.add(FrostBayResearchCard(fb_telemetry))

        # Mini SSD Card (renders presence + NOT_QUALIFIED warning)
        mini_presence = snapshot.by_id(CapabilityId.MINI_SSD_PRESENCE.value)
        mini_rel = snapshot.by_id(CapabilityId.MINI_SSD_RELIABILITY.value)
        self.peripherals_group.add(MiniSsdStatusCard(mini_presence, mini_rel))
        self.add(self.peripherals_group)

        # 3. Update Warnings Group
        self.remove(self.warnings_group)
        self.warnings_group = Adw.PreferencesGroup()
        has_warnings = False
        for rec in snapshot.capabilities:
            for warn in rec.warnings:
                has_warnings = True
                self.warnings_group.add(SafetyBanner(f"{rec.label}: {warn}", rec.safety_state))

        if has_warnings:
            self.warnings_group.set_title("Active System Warnings")
            self.add(self.warnings_group)
