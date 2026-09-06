# Super X Helper — GTK4 / Libadwaita Application Shell Walkthrough

**Target Device:** ONEXPLAYER Super X (Liquid-Cooled Edition)  
**Date:** 2026-09-06  
**Milestone:** Pre-Astra UI Shell & Read-Only Page Skeletons (`SX-UI-001` & `SX-UI-002`)  
**Status:** Completed, Verified, and Tested (29/29 tests passing)

---

## 1. Summary of Accomplishments

Built the native GTK4 / Libadwaita user interface shell and read-only page components adhering strictly to the frontend contract in `docs/UI_CONTRACT.md` and `docs/adr/0001-python-gtk-dbus-architecture.md`.

### Core Architectural Invariants Maintained
- **Zero hardware backend imports in UI:** The frontend imports only `ServiceClient`, `CapabilitySnapshot`, `CapabilityRecord`, and `ui_manifest.PAGES`.
- **Zero hardware writes:** No mutating operations or D-Bus privilege code are wired. Controls check `record.can_write` and remain visibly disabled (`set_sensitive(False)`) with informative tooltips.
- **Accurate status and safety rendering:**
  - `CONFIRMED_LOCAL`: Success badge (e.g. Diagnostics export).
  - `SUPPORTED_UNVERIFIED`: Warning badge (e.g. CPU Boost, Fan control, EPP, Brightness).
  - `READ_ONLY`: Neutral badge (e.g. Display mode, Battery telemetry, Mini SSD presence).
  - `RESEARCH_PENDING`: Accent badge (e.g. Frost Bay telemetry and control).
  - `UNAVAILABLE`: Dimmed badge (e.g. Battery charge control, RGB).
  - `NOT_QUALIFIED`: Distinct caution banner on Mini SSD storage ("Do not use as the only copy of important data until reliability qualification passes").
  - `BLOCKED`: Dedicated Frost Bay card ("Linux protocol/health semantics not validated").

---

## 2. Implemented Components

### 1. Reusable Capability Widgets (`src/superx_helper/ui/widgets.py`)
- `StatusBadge`: Pill badge styling for all 6 `CapabilityStatus` states.
- `SafetyBanner`: Adwaita card banner displaying warning icons and text for `NOT_QUALIFIED`, `WARNING`, and `BLOCKED` states.
- `CapabilityRow`: Standard `Adw.ActionRow` displaying capability label, observed values, allowed ranges, backend ownership, and disabled interactive controls (`Gtk.Switch`, `Gtk.Scale`) when `can_write == False`.
- `FrostBayResearchCard`: Dedicated card prominently displaying the `RESEARCH_PENDING` / `BLOCKED` status without presenting mock or fake telemetry.
- `MiniSsdStatusCard`: Dedicated card displaying PCIe/NVMe enumeration status alongside the required `NOT_QUALIFIED` caution banner.

### 2. Page Skeletons (`src/superx_helper/ui/pages/`)
Mapped 1:1 against `ui_manifest.PAGES`:
- `DashboardPage` (`dashboard`): Active profile indicator, platform quick-status rows, Frost Bay research card, Mini SSD presence/reliability card, and active system warnings group.
- `PerformancePage` (`performance`): CPU boost, EPP preference, power target rows, plus notice that the 120W liquid turbo envelope is blocked.
- `CoolingPage` (`cooling`): Internal fan telemetry/controls row and Frost Bay external cooling dock card.
- `DisplayPage` (`display`): Display mode and brightness rows.
- `PowerPage` (`power`): Battery telemetry, charge control (unavailable), CPU boost, and EPP.
- `StoragePage` (`storage`): Mini SSD presence and MiniSsdStatusCard with NOT_QUALIFIED warning.
- `ProfilesPage` (`profiles`): Declarative profiles list (Quiet, Balanced, Performance, Liquid Turbo) rendered in read-only mode.
- `DiagnosticsPage` (`diagnostics`): Diagnostics export row and baseline report information.

### 3. Application Window & Shell (`src/superx_helper/ui/window.py` & `src/superx_helper/ui/app.py`)
- `SuperXWindow`: Libadwaita window with `Adw.ToolbarView`, HeaderBar with title, subtitle, refresh button, responsive sidebar navigation list, and `Adw.ViewStack`.
- `SuperXApplication`: `Adw.Application` (`org.sonoran.SuperXHelper`) with `--test-run` CLI flag for headless and automated testing.
- `pyproject.toml`: Configured entry points `superx-ui` and `superx-app`.

---

## 3. Verification & Test Suite

### Automated Unit Tests
Added `tests/test_ui_widgets.py` covering all widget variants, page instantiations, capability updates, and window creation.

Running the full test suite:
```bash
$ PYTHONPATH=src python3 -m unittest discover -s tests -v
test_dmi_mock (test_collector.CollectorTests.test_dmi_mock) ... ok
test_hwmon_mock (test_collector.CollectorTests.test_hwmon_mock) ... ok
test_identifier_redaction_is_default_safe (test_collector.CollectorTests.test_identifier_redaction_is_default_safe) ... ok
test_missing_read (test_collector.CollectorTests.test_missing_read) ... ok
test_read_helpers (test_collector.CollectorTests.test_read_helpers) ... ok
test_frost_bay_is_research_pending (test_contracts.CapabilityContractTests.test_frost_bay_is_research_pending) ... ok
test_mini_ssd_reliability_is_not_qualified (test_contracts.CapabilityContractTests.test_mini_ssd_reliability_is_not_qualified) ... ok
test_unverified_control_stays_disabled (test_contracts.CapabilityContractTests.test_unverified_control_stays_disabled) ... ok
test_validated_control_can_be_enabled_by_contract (test_contracts.CapabilityContractTests.test_validated_control_can_be_enabled_by_contract) ... ok
test_authorized_fake_write (test_platform.PlatformTests.test_authorized_fake_write) ... ok
test_discovery_does_not_authorize_writes (test_platform.PlatformTests.test_discovery_does_not_authorize_writes) ... ok
test_failed_manual_mode_prevents_fan_duty_write (test_platform.PlatformTests.test_failed_manual_mode_prevents_fan_duty_write) ... ok
test_find_hwmon_by_name (test_platform.PlatformTests.test_find_hwmon_by_name) ... ok
test_range_checks_remain_before_write (test_platform.PlatformTests.test_range_checks_remain_before_write) ... ok
test_requested_vs_observed_mismatch_fails (test_platform.PlatformTests.test_requested_vs_observed_mismatch_fails) ... ok
test_absent (test_storage.StorageDiscoveryTests.test_absent) ... ok
test_nvme_present_requires_namespace (test_storage.StorageDiscoveryTests.test_nvme_present_requires_namespace) ... ok
test_pcie_only_without_controller (test_storage.StorageDiscoveryTests.test_pcie_only_without_controller) ... ok
test_pcie_only_without_namespace (test_storage.StorageDiscoveryTests.test_pcie_only_without_namespace) ... ok
test_storage_inventory_identifier_opt_in (test_storage.StorageDiscoveryTests.test_storage_inventory_identifier_opt_in) ... ok
test_storage_inventory_redacts_serial_by_default (test_storage.StorageDiscoveryTests.test_storage_inventory_redacts_serial_by_default) ... ok
test_expected_pages_are_stable (test_ui_manifest.UiManifestTests.test_expected_pages_are_stable) ... ok
test_all_pages_instantiation_and_update (test_ui_widgets.TestUiWidgets.test_all_pages_instantiation_and_update) ... ok
test_capability_row_disables_unverified_controls (test_ui_widgets.TestUiWidgets.test_capability_row_disables_unverified_controls) ... ok
test_frost_bay_research_card (test_ui_widgets.TestUiWidgets.test_frost_bay_research_card) ... ok
test_mini_ssd_status_card_renders_not_qualified (test_ui_widgets.TestUiWidgets.test_mini_ssd_status_card_renders_not_qualified) ... ok
test_safety_banner_creation (test_ui_widgets.TestUiWidgets.test_safety_banner_creation) ... ok
test_status_badge_variants (test_ui_widgets.TestUiWidgets.test_status_badge_variants) ... ok
test_superx_window_creation (test_ui_widgets.TestUiWidgets.test_superx_window_creation) ... ok

----------------------------------------------------------------------
Ran 29 tests in 0.318s

OK
```

### Application Shell Execution
```bash
$ PYTHONPATH=src python3 -m superx_helper.ui.app --test-run
[✓] Application shell initialized with 8 pages.
```
