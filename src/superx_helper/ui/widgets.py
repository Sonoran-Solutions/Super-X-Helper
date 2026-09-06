"""Reusable GTK4 / Libadwaita widgets for capability rendering."""

from __future__ import annotations

from typing import Optional

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk, Pango

from superx_helper.contracts import CapabilityRecord, CapabilityStatus, SafetyState


class StatusBadge(Gtk.Label):
    """Badge pill widget rendering a capability's operational status."""

    def __init__(self, status: CapabilityStatus):
        super().__init__()
        self.set_valign(Gtk.Align.CENTER)
        self.add_css_class("caption")
        self.update_status(status)

    def update_status(self, status: CapabilityStatus) -> None:
        # Clear previous state classes
        for cls in ("success", "warning", "accent", "error", "dim-label"):
            self.remove_css_class(cls)

        if status == CapabilityStatus.CONFIRMED_LOCAL:
            self.set_text("Confirmed Local")
            self.add_css_class("success")
        elif status == CapabilityStatus.SUPPORTED_UNVERIFIED:
            self.set_text("Unverified")
            self.add_css_class("warning")
        elif status == CapabilityStatus.READ_ONLY:
            self.set_text("Read-Only")
            self.add_css_class("dim-label")
        elif status == CapabilityStatus.RESEARCH_PENDING:
            self.set_text("Research Pending")
            self.add_css_class("accent")
        elif status == CapabilityStatus.UNAVAILABLE:
            self.set_text("Unavailable")
            self.add_css_class("dim-label")
        elif status == CapabilityStatus.ERROR:
            self.set_text("Error")
            self.add_css_class("error")
        else:
            self.set_text(status.value)


class SafetyBanner(Gtk.Box):
    """Warning or notice banner for safety states and cautions."""

    def __init__(self, message: str, safety_state: SafetyState = SafetyState.WARNING):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.add_css_class("card")
        self.set_margin_top(6)
        self.set_margin_bottom(6)
        self.set_margin_start(12)
        self.set_margin_end(12)

        icon_name = "dialog-warning-symbolic"
        if safety_state == SafetyState.BLOCKED:
            icon_name = "action-unavailable-symbolic"
        elif safety_state == SafetyState.NOT_QUALIFIED:
            icon_name = "dialog-warning-symbolic"

        icon = Gtk.Image.new_from_icon_name(icon_name)
        icon.set_icon_size(Gtk.IconSize.LARGE)
        icon.set_valign(Gtk.Align.CENTER)
        self.append(icon)

        label = Gtk.Label(label=message)
        label.set_wrap(True)
        label.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
        label.set_xalign(0.0)
        label.set_hexpand(True)
        self.append(label)


class CapabilityRow(Adw.ActionRow):
    """Standard Libadwaita row rendering a single CapabilityRecord."""

    def __init__(self, record: CapabilityRecord):
        super().__init__()
        self.record = record
        self.set_title(record.label)

        # Construct subtitle describing observed value and status
        sub_parts = []
        if record.observed_value is not None:
            val_str = f"{record.observed_value}"
            if record.unit:
                val_str += f" {record.unit}"
            sub_parts.append(f"Observed: {val_str}")
        elif record.reason_unavailable:
            sub_parts.append(record.reason_unavailable)
        else:
            sub_parts.append(f"Backend: {record.backend} ({record.owner})")

        if record.allowed_values and not record.can_write:
            sub_parts.append(f"Allowed: {', '.join(str(v) for v in record.allowed_values)}")

        self.set_subtitle(" • ".join(sub_parts))

        # Add StatusBadge suffix
        self.badge = StatusBadge(record.status)
        self.add_suffix(self.badge)

        # Add disabled control placeholder reflecting write state
        if record.write_supported:
            if record.allowed_values == [False, True]:
                sw = Gtk.Switch()
                sw.set_valign(Gtk.Align.CENTER)
                sw.set_active(bool(record.observed_value))
                sw.set_sensitive(record.can_write)
                if not record.can_write:
                    sw.set_tooltip_text(
                        "Hardware writes are disabled: capability is unverified/unauthorized in this phase."
                    )
                self.add_suffix(sw)
            elif record.minimum is not None and record.maximum is not None:
                scale = Gtk.Scale.new_with_range(
                    Gtk.Orientation.HORIZONTAL, record.minimum, record.maximum, 1.0
                )
                scale.set_valign(Gtk.Align.CENTER)
                scale.set_size_request(120, -1)
                if isinstance(record.observed_value, (int, float)):
                    scale.set_value(float(record.observed_value))
                scale.set_sensitive(record.can_write)
                if not record.can_write:
                    scale.set_tooltip_text(
                        "Control is read-only: writes are disabled pending local validation."
                    )
                self.add_suffix(scale)


class FrostBayResearchCard(Gtk.Box):
    """Explicit Adwaita card rendering the Frost Bay research-pending status."""

    def __init__(self, record_telemetry: Optional[CapabilityRecord] = None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.add_css_class("card")
        self.set_margin_top(6)
        self.set_margin_bottom(6)
        self.set_margin_start(12)
        self.set_margin_end(12)

        # Title row
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        icon = Gtk.Image.new_from_icon_name("weather-snow-symbolic")
        icon.set_icon_size(Gtk.IconSize.LARGE)
        header.append(icon)

        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        title_box.set_hexpand(True)
        title = Gtk.Label(label="Frost Bay Liquid Cooler")
        title.add_css_class("heading")
        title.set_xalign(0.0)
        title_box.append(title)

        status_text = Gtk.Label(label="Research Pending • Writes Blocked")
        status_text.add_css_class("dim-label")
        status_text.add_css_class("caption")
        status_text.set_xalign(0.0)
        title_box.append(status_text)
        header.append(title_box)

        badge = StatusBadge(CapabilityStatus.RESEARCH_PENDING)
        header.append(badge)
        self.append(header)

        # Notice text
        desc = Gtk.Label(
            label="Linux Bluetooth protocol and health semantics are not yet validated. "
            "No hardware controls or mock telemetry are enabled until Phase 1 research completes."
        )
        desc.set_wrap(True)
        desc.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
        desc.set_xalign(0.0)
        desc.add_css_class("dim-label")
        self.append(desc)


class MiniSsdStatusCard(Gtk.Box):
    """Adwaita card rendering Mini SSD presence alongside NOT_QUALIFIED reliability status."""

    def __init__(
        self,
        presence: Optional[CapabilityRecord] = None,
        reliability: Optional[CapabilityRecord] = None,
    ):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.add_css_class("card")
        self.set_margin_top(6)
        self.set_margin_bottom(6)
        self.set_margin_start(12)
        self.set_margin_end(12)

        # Header
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        icon = Gtk.Image.new_from_icon_name("drive-harddisk-symbolic")
        icon.set_icon_size(Gtk.IconSize.LARGE)
        header.append(icon)

        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        title_box.set_hexpand(True)
        title = Gtk.Label(label="Removable Mini SSD Slot")
        title.add_css_class("heading")
        title.set_xalign(0.0)
        title_box.append(title)

        state_str = (
            f"State: {presence.observed_value}"
            if (presence and presence.observed_value)
            else "State: Detected"
        )
        state_label = Gtk.Label(label=state_str)
        state_label.add_css_class("dim-label")
        state_label.add_css_class("caption")
        state_label.set_xalign(0.0)
        title_box.append(state_label)
        header.append(title_box)

        # Badges
        if presence:
            header.append(StatusBadge(presence.status))
        self.append(header)

        # Reliability warning
        warning_msg = (
            "Reliability: NOT QUALIFIED\n"
            "Do not use the Mini SSD as the only copy of important data until qualification testing passes."
        )
        banner = SafetyBanner(warning_msg, SafetyState.NOT_QUALIFIED)
        self.append(banner)
