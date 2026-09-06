"""Diagnostics and telemetry export page."""

from __future__ import annotations

from typing import Optional

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

from superx_helper.contracts import CapabilityId, CapabilitySnapshot
from superx_helper.ui.pages.base import BasePage
from superx_helper.ui_manifest import PageSpec


class DiagnosticsPage(BasePage):
    """Diagnostics and system snapshot export page."""

    def __init__(self, spec: Optional[PageSpec] = None):
        super().__init__(
            spec
            or PageSpec(
                "diagnostics",
                "Diagnostics",
                [CapabilityId.DIAGNOSTICS_EXPORT.value],
            )
        )

        self.info_group = Adw.PreferencesGroup()
        self.info_group.set_title("System Baseline and Troubleshooting")

        row = Adw.ActionRow()
        row.set_title("Immutable Hardware Baseline")
        row.set_subtitle("Recorded in docs/local-hardware-baseline.md")
        self.info_group.add(row)

        export_row = Adw.ActionRow()
        export_row.set_title("Generate Diagnostic Report")
        export_row.set_subtitle("Exports non-sensitive JSON snapshot via CLI: superx-diag -o [file]")
        self.info_group.add(export_row)

        self.add(self.info_group)
