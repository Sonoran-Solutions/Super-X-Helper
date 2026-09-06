#!/usr/bin/env python3
"""Unit tests for Super X Helper GTK4 / Libadwaita UI components."""

import unittest

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

from superx_helper.contracts import (
    CapabilityId,
    CapabilityRecord,
    CapabilitySnapshot,
    CapabilityStatus,
    SafetyState,
)
from superx_helper.ui.pages import (
    BasePage,
    CoolingPage,
    DashboardPage,
    DiagnosticsPage,
    DisplayPage,
    PerformancePage,
    PowerPage,
    ProfilesPage,
    StoragePage,
)
from superx_helper.ui.widgets import (
    CapabilityRow,
    FrostBayResearchCard,
    MiniSsdStatusCard,
    SafetyBanner,
    StatusBadge,
)
from superx_helper.ui.window import SuperXWindow
from superx_helper.ui_manifest import PAGES, PageSpec


class MockServiceClient:
    def __init__(self, snapshot: CapabilitySnapshot):
        self.snapshot = snapshot

    def get_snapshot(self) -> CapabilitySnapshot:
        return self.snapshot


def create_test_snapshot() -> CapabilitySnapshot:
    caps = [
        CapabilityRecord(
            capability_id=CapabilityId.CPU_BOOST.value,
            label="CPU Boost",
            status=CapabilityStatus.SUPPORTED_UNVERIFIED,
            read_supported=True,
            write_supported=True,
            locally_validated=False,
            observed_value=True,
            allowed_values=[False, True],
            safety_state=SafetyState.WARNING,
        ),
        CapabilityRecord(
            capability_id=CapabilityId.INTERNAL_FAN.value,
            label="Internal Fan Duty",
            status=CapabilityStatus.SUPPORTED_UNVERIFIED,
            read_supported=True,
            write_supported=True,
            locally_validated=False,
            observed_value=45,
            minimum=0.0,
            maximum=100.0,
            unit="%",
            safety_state=SafetyState.WARNING,
        ),
        CapabilityRecord(
            capability_id=CapabilityId.FROST_BAY_TELEMETRY.value,
            label="Frost Bay Telemetry",
            status=CapabilityStatus.RESEARCH_PENDING,
            read_supported=False,
            write_supported=False,
            locally_validated=False,
            safety_state=SafetyState.BLOCKED,
        ),
        CapabilityRecord(
            capability_id=CapabilityId.MINI_SSD_PRESENCE.value,
            label="Mini SSD Presence",
            status=CapabilityStatus.READ_ONLY,
            read_supported=True,
            write_supported=False,
            locally_validated=True,
            observed_value="NVME_PRESENT",
            safety_state=SafetyState.NORMAL,
        ),
        CapabilityRecord(
            capability_id=CapabilityId.MINI_SSD_RELIABILITY.value,
            label="Mini SSD Reliability",
            status=CapabilityStatus.READ_ONLY,
            read_supported=True,
            write_supported=False,
            locally_validated=False,
            observed_value="NOT_QUALIFIED",
            safety_state=SafetyState.NOT_QUALIFIED,
            warnings=["Do not use as the only copy of important data."],
        ),
        CapabilityRecord(
            capability_id=CapabilityId.BATTERY_CHARGE_CONTROL.value,
            label="Battery Charge Control",
            status=CapabilityStatus.UNAVAILABLE,
            read_supported=False,
            write_supported=False,
            locally_validated=False,
            reason_unavailable="Not exposed via standard ACPI",
            safety_state=SafetyState.UNKNOWN,
        ),
        CapabilityRecord(
            capability_id=CapabilityId.DIAGNOSTICS_EXPORT.value,
            label="Diagnostic Report Export",
            status=CapabilityStatus.CONFIRMED_LOCAL,
            read_supported=True,
            write_supported=False,
            locally_validated=True,
            safety_state=SafetyState.NORMAL,
        ),
    ]
    return CapabilitySnapshot(
        schema_version=1,
        generated_at="2026-09-06T23:00:00Z",
        capabilities=caps,
    )


class TestUiWidgets(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Adw.init()

    def test_status_badge_variants(self):
        badge = StatusBadge(CapabilityStatus.CONFIRMED_LOCAL)
        self.assertEqual(badge.get_text(), "Confirmed Local")

        badge.update_status(CapabilityStatus.SUPPORTED_UNVERIFIED)
        self.assertEqual(badge.get_text(), "Unverified")

        badge.update_status(CapabilityStatus.READ_ONLY)
        self.assertEqual(badge.get_text(), "Read-Only")

        badge.update_status(CapabilityStatus.RESEARCH_PENDING)
        self.assertEqual(badge.get_text(), "Research Pending")

        badge.update_status(CapabilityStatus.UNAVAILABLE)
        self.assertEqual(badge.get_text(), "Unavailable")

        badge.update_status(CapabilityStatus.ERROR)
        self.assertEqual(badge.get_text(), "Error")

    def test_safety_banner_creation(self):
        banner = SafetyBanner("Test Warning", SafetyState.NOT_QUALIFIED)
        self.assertIsNotNone(banner)
        self.assertTrue(banner.has_css_class("card"))

    def test_capability_row_disables_unverified_controls(self):
        snapshot = create_test_snapshot()
        boost_rec = snapshot.by_id(CapabilityId.CPU_BOOST.value)
        self.assertIsNotNone(boost_rec)
        self.assertFalse(boost_rec.can_write)

        row = CapabilityRow(boost_rec)
        self.assertEqual(row.get_title(), "CPU Boost")
        self.assertIn("Observed: True", row.get_subtitle())

        fan_rec = snapshot.by_id(CapabilityId.INTERNAL_FAN.value)
        self.assertIsNotNone(fan_rec)
        self.assertFalse(fan_rec.can_write)
        row_fan = CapabilityRow(fan_rec)
        self.assertEqual(row_fan.get_title(), "Internal Fan Duty")
        self.assertIn("Observed: 45 %", row_fan.get_subtitle())

    def test_frost_bay_research_card(self):
        snapshot = create_test_snapshot()
        fb_rec = snapshot.by_id(CapabilityId.FROST_BAY_TELEMETRY.value)
        card = FrostBayResearchCard(fb_rec)
        self.assertIsNotNone(card)
        self.assertTrue(card.has_css_class("card"))

    def test_mini_ssd_status_card_renders_not_qualified(self):
        snapshot = create_test_snapshot()
        presence = snapshot.by_id(CapabilityId.MINI_SSD_PRESENCE.value)
        rel = snapshot.by_id(CapabilityId.MINI_SSD_RELIABILITY.value)
        card = MiniSsdStatusCard(presence, rel)
        self.assertIsNotNone(card)
        self.assertTrue(card.has_css_class("card"))

    def test_all_pages_instantiation_and_update(self):
        snapshot = create_test_snapshot()
        page_classes = [
            (DashboardPage, "dashboard"),
            (PerformancePage, "performance"),
            (CoolingPage, "cooling"),
            (DisplayPage, "display"),
            (PowerPage, "power"),
            (StoragePage, "storage"),
            (ProfilesPage, "profiles"),
            (DiagnosticsPage, "diagnostics"),
        ]

        for cls, page_id in page_classes:
            spec = next((p for p in PAGES if p.page_id == page_id), PageSpec(page_id, page_id.title(), []))
            page = cls(spec)
            self.assertIsNotNone(page)
            page.update_from_snapshot(snapshot)

    def test_superx_window_creation(self):
        app = Adw.Application(application_id="org.sonoran.SuperXHelper.Test")
        app.register()
        snapshot = create_test_snapshot()
        client = MockServiceClient(snapshot)

        window = SuperXWindow(app, client)
        self.assertEqual(len(window.pages), len(PAGES))
        self.assertIn("dashboard", window.pages)
        self.assertIn("performance", window.pages)
        self.assertIn("cooling", window.pages)
        self.assertIn("storage", window.pages)


if __name__ == "__main__":
    unittest.main()
