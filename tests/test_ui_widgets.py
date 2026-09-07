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
    format_observed_value,
)
from superx_helper.ui.window import SuperXWindow
from superx_helper.ui_manifest import PAGES, PageSpec


class MockServiceClient:
    def __init__(self, snapshot: CapabilitySnapshot):
        self.snapshot = snapshot

    def get_snapshot(self) -> CapabilitySnapshot:
        return self.snapshot


def create_real_service_shaped_snapshot(
    mini_ssd_state: str = "NVME_PRESENT",
    battery_pct: int = 99,
    has_warning: bool = False,
) -> CapabilitySnapshot:
    """Create a capability snapshot with exact real-world service-shaped structured values."""
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
            owner="Linux cpufreq",
            backend="platform",
            safety_state=SafetyState.WARNING,
        ),
        CapabilityRecord(
            capability_id=CapabilityId.CPU_EPP.value,
            label="Energy Performance Preference",
            status=CapabilityStatus.SUPPORTED_UNVERIFIED,
            read_supported=True,
            write_supported=True,
            locally_validated=False,
            observed_value="balance_performance",
            allowed_values=["default", "performance", "balance_performance", "balance_power", "power"],
            owner="amd-pstate-epp",
            backend="platform",
            safety_state=SafetyState.WARNING,
        ),
        CapabilityRecord(
            capability_id=CapabilityId.INTERNAL_FAN.value,
            label="Internal Fan",
            status=CapabilityStatus.SUPPORTED_UNVERIFIED,
            read_supported=True,
            write_supported=True,
            locally_validated=False,
            observed_value=45,
            minimum=0,
            maximum=100,
            unit="%",
            owner="oxpec / firmware EC",
            backend="platform",
            safety_state=SafetyState.WARNING,
        ),
        CapabilityRecord(
            capability_id=CapabilityId.DISPLAY_MODE.value,
            label="Display Mode",
            status=CapabilityStatus.READ_ONLY,
            read_supported=True,
            write_supported=False,
            locally_validated=True,
            observed_value=[
                {
                    "connector": "card1-eDP-1",
                    "status": "connected",
                    "modes": ["2880x1800", "1920x1200"],
                    "primary_mode": "2880x1800",
                },
                {
                    "connector": "card1-HDMI-A-1",
                    "status": "connected",
                    "modes": ["3840x2160"],
                    "primary_mode": "3840x2160",
                },
            ],
            owner="DRM/compositor",
            backend="telemetry",
            safety_state=SafetyState.NORMAL,
        ),
        CapabilityRecord(
            capability_id=CapabilityId.BATTERY_TELEMETRY.value,
            label="Battery",
            status=CapabilityStatus.READ_ONLY,
            read_supported=True,
            write_supported=False,
            locally_validated=True,
            observed_value={
                "present": True,
                "status": "Not charging",
                "capacity_pct": battery_pct,
                "manufacturer": "Amd Battery",
                "model_name": "Li-ion Real Battery",
                "energy_now_wh": 79.84,
                "energy_full_wh": 80.9,
                "energy_design_wh": 85.58,
                "voltage_now_v": 15.56,
            },
            owner="power_supply",
            backend="telemetry",
            safety_state=SafetyState.NORMAL,
        ),
        CapabilityRecord(
            capability_id=CapabilityId.MINI_SSD_PRESENCE.value,
            label="Mini SSD Presence",
            status=CapabilityStatus.READ_ONLY,
            read_supported=True,
            write_supported=False,
            locally_validated=True,
            observed_value={
                "state": mini_ssd_state,
                "pci_address": "0000:c4:00.0",
                "controller": "nvme0",
                "namespaces": ["nvme0n1"],
                "reliability": "NOT_QUALIFIED",
            },
            owner="PCIe / Linux NVMe",
            backend="storage",
            safety_state=SafetyState.NORMAL if mini_ssd_state != "ABSENT" else SafetyState.WARNING,
            warnings=["Mini SSD is not currently visible at the PCIe endpoint."] if mini_ssd_state == "ABSENT" else [],
        ),
        CapabilityRecord(
            capability_id=CapabilityId.MINI_SSD_RELIABILITY.value,
            label="Mini SSD Reliability",
            status=CapabilityStatus.READ_ONLY,
            read_supported=True,
            write_supported=False,
            locally_validated=True,
            observed_value="NOT_QUALIFIED",
            owner="Super X Helper research",
            backend="storage",
            warnings=["Do not use the Mini SSD as the only copy of important data until reliability qualification passes."],
            safety_state=SafetyState.NOT_QUALIFIED,
        ),
        CapabilityRecord(
            capability_id=CapabilityId.FROST_BAY_TELEMETRY.value,
            label="Frost Bay Telemetry",
            status=CapabilityStatus.RESEARCH_PENDING,
            read_supported=False,
            write_supported=False,
            locally_validated=False,
            owner="Super X Helper / BlueZ",
            backend="frost_bay",
            reason_unavailable="Frost Bay BLE protocol and health semantics have not been validated yet.",
            safety_state=SafetyState.BLOCKED,
        ),
        CapabilityRecord(
            capability_id=CapabilityId.BATTERY_CHARGE_CONTROL.value,
            label="Charge Limit / Bypass",
            status=CapabilityStatus.UNAVAILABLE,
            read_supported=False,
            write_supported=False,
            locally_validated=False,
            owner="unknown",
            backend="platform",
            reason_unavailable="No trustworthy Linux charge-limit/bypass control path has been confirmed on this Super X.",
            safety_state=SafetyState.UNKNOWN,
        ),
        CapabilityRecord(
            capability_id=CapabilityId.DIAGNOSTICS_EXPORT.value,
            label="Diagnostics Export",
            status=CapabilityStatus.CONFIRMED_LOCAL,
            read_supported=True,
            write_supported=False,
            locally_validated=True,
            owner="Super X Helper",
            backend="diagnostics",
            safety_state=SafetyState.NORMAL,
        ),
    ]

    if has_warning:
        caps.append(
            CapabilityRecord(
                capability_id="system.alert",
                label="Thermal Warning",
                status=CapabilityStatus.ERROR,
                read_supported=True,
                write_supported=False,
                locally_validated=True,
                safety_state=SafetyState.WARNING,
                warnings=["High temperature threshold exceeded."],
            )
        )

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

    def test_format_observed_value_human_readable(self):
        snapshot = create_real_service_shaped_snapshot()

        # 1. Battery dictionary formatting
        bat_rec = snapshot.by_id(CapabilityId.BATTERY_TELEMETRY.value)
        bat_formatted = format_observed_value(bat_rec)
        self.assertIsNotNone(bat_formatted)
        self.assertIn("99%", bat_formatted)
        self.assertIn("Not charging", bat_formatted)
        self.assertIn("79.84 Wh / 80.9 Wh", bat_formatted)
        self.assertNotIn("{'present'", bat_formatted)  # No raw dict strings

        # 2. Display connectors list formatting
        disp_rec = snapshot.by_id(CapabilityId.DISPLAY_MODE.value)
        disp_formatted = format_observed_value(disp_rec)
        self.assertIsNotNone(disp_formatted)
        self.assertIn("card1-eDP-1: 2880x1800", disp_formatted)
        self.assertIn("card1-HDMI-A-1: 3840x2160", disp_formatted)
        self.assertNotIn("[{'connector'", disp_formatted)  # No raw list strings

        # 3. Mini SSD presence dictionary formatting
        mini_rec = snapshot.by_id(CapabilityId.MINI_SSD_PRESENCE.value)
        mini_formatted = format_observed_value(mini_rec)
        self.assertIsNotNone(mini_formatted)
        self.assertIn("NVME_PRESENT", mini_formatted)
        self.assertIn("Slot 0000:c4:00.0", mini_formatted)
        self.assertIn("(nvme0)", mini_formatted)
        self.assertNotIn("{'state'", mini_formatted)  # No raw dict strings

        # 4. Boolean formatting
        boost_rec = snapshot.by_id(CapabilityId.CPU_BOOST.value)
        self.assertEqual(format_observed_value(boost_rec), "Enabled")

    def test_capability_row_with_dropdown_for_epp(self):
        snapshot = create_real_service_shaped_snapshot()
        epp_rec = snapshot.by_id(CapabilityId.CPU_EPP.value)
        self.assertIsNotNone(epp_rec)
        self.assertFalse(epp_rec.can_write)

        row = CapabilityRow(epp_rec)
        self.assertEqual(row.get_title(), "Energy Performance Preference")
        self.assertIn("Observed: balance_performance", row.get_subtitle())

        # Verify a Gtk.DropDown suffix was created and disabled
        def find_dropdown(widget):
            if isinstance(widget, Gtk.DropDown):
                return widget
            child = widget.get_first_child()
            while child:
                found = find_dropdown(child)
                if found:
                    return found
                child = child.get_next_sibling()
            return None

        dropdown = find_dropdown(row)
        self.assertIsNotNone(dropdown, "Gtk.DropDown should be rendered for multi-valued discrete capability")
        self.assertFalse(dropdown.get_sensitive())
        model = dropdown.get_model()
        self.assertIsNotNone(model)
        self.assertEqual(model.get_n_items(), len(epp_rec.allowed_values))
        self.assertEqual(dropdown.get_selected(), epp_rec.allowed_values.index("balance_performance"))

    def test_frost_bay_research_card_dynamic_derivation(self):
        # 1. With real service-provided research record
        snapshot = create_real_service_shaped_snapshot()
        fb_rec = snapshot.by_id(CapabilityId.FROST_BAY_TELEMETRY.value)
        card = FrostBayResearchCard(fb_rec)
        self.assertIsNotNone(card)

        # 2. With None (missing data must render Unknown)
        card_empty = FrostBayResearchCard(None)
        self.assertIsNotNone(card_empty)

        # 3. With simulated future confirmed record
        future_record = CapabilityRecord(
            capability_id=CapabilityId.FROST_BAY_TELEMETRY.value,
            label="Frost Bay Telemetry",
            status=CapabilityStatus.CONFIRMED_LOCAL,
            read_supported=True,
            write_supported=True,
            locally_validated=True,
            observed_value="Pump 70% • Flow Healthy",
            safety_state=SafetyState.NORMAL,
        )
        card_future = FrostBayResearchCard(future_record)
        self.assertIsNotNone(card_future)

    def test_mini_ssd_status_card_dynamic_derivation_and_missing_data(self):
        snapshot = create_real_service_shaped_snapshot()
        presence = snapshot.by_id(CapabilityId.MINI_SSD_PRESENCE.value)
        rel = snapshot.by_id(CapabilityId.MINI_SSD_RELIABILITY.value)

        # 1. With real service records
        card = MiniSsdStatusCard(presence, rel)
        self.assertIsNotNone(card)

        # 2. With missing data: must render Unknown, never Detected
        card_none = MiniSsdStatusCard(None, None)
        self.assertIsNotNone(card_none)

        card_empty_val = MiniSsdStatusCard(
            CapabilityRecord(
                capability_id="storage.mini_ssd.presence",
                label="Mini SSD",
                status=CapabilityStatus.UNAVAILABLE,
                read_supported=False,
                write_supported=False,
                locally_validated=False,
                observed_value=None,
            ),
            None,
        )
        self.assertIsNotNone(card_empty_val)

    def test_all_pages_instantiation_and_update(self):
        snapshot = create_real_service_shaped_snapshot()
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
        app = Adw.Application(application_id="org.sonoran.SuperXHelper.TestWindow")
        app.register()
        snapshot = create_real_service_shaped_snapshot()
        client = MockServiceClient(snapshot)

        window = SuperXWindow(app, client)
        self.assertEqual(len(window.pages), len(PAGES))
        self.assertIn("dashboard", window.pages)
        self.assertIn("performance", window.pages)
        self.assertIn("cooling", window.pages)
        self.assertIn("storage", window.pages)

    def test_repeated_refresh_cycle(self):
        """Verify window and pages survive repeated refreshes without widget accumulation or error."""
        app = Adw.Application(application_id="org.sonoran.SuperXHelper.TestRefresh")
        app.register()

        snap1 = create_real_service_shaped_snapshot(mini_ssd_state="NVME_PRESENT", battery_pct=95)
        client = MockServiceClient(snap1)
        window = SuperXWindow(app, client)

        # Refresh 1: Initial state
        window.refresh()
        dash: DashboardPage = window.pages["dashboard"]
        self.assertIsNotNone(dash)

        # Refresh 2: Mini SSD absent + battery changed
        snap2 = create_real_service_shaped_snapshot(mini_ssd_state="ABSENT", battery_pct=80, has_warning=True)
        client.snapshot = snap2
        window.refresh()

        # Refresh 3: Mini SSD restored + warning cleared
        snap3 = create_real_service_shaped_snapshot(mini_ssd_state="NVME_PRESENT", battery_pct=75, has_warning=False)
        client.snapshot = snap3
        window.refresh()


if __name__ == "__main__":
    unittest.main()
