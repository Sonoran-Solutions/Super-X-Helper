"""Reusable GTK4 / Libadwaita widgets for capability rendering."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk, Pango

from superx_helper.contracts import (
    CapabilityId,
    CapabilityRecord,
    CapabilityStatus,
    SafetyState,
)


def _format_battery(val: Any) -> Optional[str]:
    if not isinstance(val, dict) or "capacity_pct" not in val:
        return None
    parts: List[str] = []
    pct = val.get("capacity_pct")
    if pct is not None:
        parts.append(f"{pct}%")
    st = val.get("status")
    if st:
        parts.append(str(st))
    now = val.get("energy_now_wh")
    full = val.get("energy_full_wh")
    if now is not None and full is not None:
        parts.append(f"({now} Wh / {full} Wh)")
    return " • ".join(parts) if parts else "Present"


def _format_display_connectors(val: Any) -> Optional[str]:
    if not isinstance(val, list):
        return None
    conn_strs = []
    for item in val:
        if isinstance(item, dict) and item.get("status") == "connected":
            conn_name = item.get("connector", "Display")
            mode = item.get("primary_mode") or "Connected"
            conn_strs.append(f"{conn_name}: {mode}")
    return ", ".join(conn_strs) if conn_strs else "No active displays"


def format_mini_ssd_telemetry(val: Any) -> Optional[str]:
    """Format optional link/temperature fields from the service contract."""
    if not isinstance(val, dict):
        return None
    generations = {2.5: "Gen1", 5.0: "Gen2", 8.0: "Gen3", 16.0: "Gen4", 32.0: "Gen5", 64.0: "Gen6"}

    def speed_number(speed: Any) -> Optional[float]:
        try:
            return float(str(speed).split()[0])
        except (ValueError, IndexError):
            return None

    def link_text(speed: Any, width: Any) -> str:
        parts = [str(generations.get(speed_number(speed), speed))] if speed else []
        if width is not None:
            parts.append(f"x{width}")
        return " ".join(parts)

    speed, width = val.get("link_speed"), val.get("link_width")
    max_speed, max_width = val.get("max_link_speed"), val.get("max_link_width")
    link = link_text(speed, width)
    speeds = speed_number(speed), speed_number(max_speed)
    slower = all(s is not None for s in speeds) and speeds[0] < speeds[1]
    narrower = isinstance(width, int) and isinstance(max_width, int) and width < max_width
    if link and (slower or narrower):
        link += f" (max {link_text(max_speed, max_width)})"
    parts = [link] if link else []
    temperature = val.get("temperature_c")
    if isinstance(temperature, (int, float)):
        parts.append(f"{temperature:.1f} °C")
    return " · ".join(parts) or None


def _format_mini_ssd_presence(val: Any) -> Optional[str]:
    if not isinstance(val, dict) or "state" not in val:
        return None
    state_name = str(val.get("state", "Unknown"))
    parts = [state_name]
    pci = val.get("pci_address")
    if pci:
        parts.append(f"Slot {pci}")
    ctrl = val.get("controller")
    if ctrl:
        parts.append(f"({ctrl})")
    telemetry = format_mini_ssd_telemetry(val)
    if telemetry:
        parts.append(telemetry)
    return " • ".join(parts)


def format_observed_value(record: CapabilityRecord) -> Optional[str]:
    """Return capability-aware, human-readable representation for observed values.

    Dispatch is keyed on the stable ``capability_id`` first, then the expected
    data shape is validated.  We never infer meaning from value shape alone, so
    a list on a non-display capability or a ``state`` dict on a non-storage
    capability is not misread as another capability's telemetry.
    """
    val = record.observed_value
    if val is None:
        return None

    cid = record.capability_id

    if cid == CapabilityId.BATTERY_TELEMETRY.value:
        formatted = _format_battery(val)
        if formatted is not None:
            return formatted

    if cid == CapabilityId.DISPLAY_MODE.value:
        formatted = _format_display_connectors(val)
        if formatted is not None:
            return formatted

    if cid == CapabilityId.MINI_SSD_PRESENCE.value:
        formatted = _format_mini_ssd_presence(val)
        if formatted is not None:
            return formatted

    # Scalar fallbacks
    if isinstance(val, bool):
        return "Enabled" if val else "Disabled"

    if record.unit:
        return f"{val} {record.unit}"

    return str(val)


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
    """Standard Libadwaita row rendering a single CapabilityRecord.

    When ``record.can_write`` and an ``on_set`` callback are both present, the
    row control is wired to ``on_set(capability_id, value)``.  Signals are
    connected only after the initial value is applied, so building a row never
    emits a write.  Writability is derived exclusively from the contract.
    """

    SCALE_DEBOUNCE_MS = 400

    def __init__(
        self,
        record: CapabilityRecord,
        on_set: Optional[Callable[[str, Any], None]] = None,
    ):
        super().__init__()
        self.record = record
        self.on_set = on_set
        self._scale_source_id: Optional[int] = None
        self.set_title(record.label)

        connect_control = record.can_write and on_set is not None

        # Construct subtitle using capability-aware formatting
        sub_parts = []
        val_str = format_observed_value(record)
        if val_str is not None:
            sub_parts.append(f"Observed: {val_str}")
        elif record.reason_unavailable:
            sub_parts.append(record.reason_unavailable)
        else:
            sub_parts.append(f"Backend: {record.backend} ({record.owner})")

        # Mention allowed values in subtitle only if discrete control is not rendered
        is_boolean = record.allowed_values == [False, True]
        has_dropdown = bool(record.allowed_values and len(record.allowed_values) > 1 and not is_boolean)

        if record.allowed_values and not record.can_write and not has_dropdown:
            sub_parts.append(f"Allowed: {', '.join(str(v) for v in record.allowed_values)}")

        self.set_subtitle(" • ".join(sub_parts))

        # Add StatusBadge suffix
        self.badge = StatusBadge(record.status)
        self.add_suffix(self.badge)

        # Add disabled control placeholder reflecting write state
        if record.write_supported:
            if is_boolean:
                sw = Gtk.Switch()
                sw.set_valign(Gtk.Align.CENTER)
                sw.set_active(bool(record.observed_value))
                sw.set_sensitive(record.can_write)
                if not record.can_write:
                    sw.set_tooltip_text(
                        "Hardware writes are disabled: capability is unverified/unauthorized in this phase."
                    )
                if connect_control:
                    sw.connect("notify::active", self._on_switch_active)
                self.add_suffix(sw)
                self.control = sw
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
                if connect_control:
                    scale.connect("value-changed", self._on_scale_value_changed)
                self.add_suffix(scale)
                self.control = scale
            elif has_dropdown:
                # Multiple discrete allowed values (e.g. EPP preferences)
                str_items = [str(v) for v in record.allowed_values]
                string_list = Gtk.StringList.new(str_items)
                drop_down = Gtk.DropDown.new(string_list, None)
                drop_down.set_valign(Gtk.Align.CENTER)
                if record.observed_value is not None and str(record.observed_value) in str_items:
                    drop_down.set_selected(str_items.index(str(record.observed_value)))
                drop_down.set_sensitive(record.can_write)
                if not record.can_write:
                    drop_down.set_tooltip_text(
                        "Control is read-only: writes are disabled pending local validation."
                    )
                if connect_control:
                    drop_down.connect("notify::selected", self._on_dropdown_selected)
                self.add_suffix(drop_down)
                self.control = drop_down

    def _emit_set(self, value: Any) -> None:
        """Forward a user-originated value, skipping no-op writes."""
        if self.on_set is None or value == self.record.observed_value:
            return
        self.on_set(self.record.capability_id, value)

    def _on_switch_active(self, switch: Gtk.Switch, _pspec) -> None:
        self._emit_set(bool(switch.get_active()))

    def _on_dropdown_selected(self, drop_down: Gtk.DropDown, _pspec) -> None:
        index = drop_down.get_selected()
        values = self.record.allowed_values
        if index == Gtk.INVALID_LIST_POSITION or index >= len(values):
            return
        self._emit_set(values[index])

    def _on_scale_value_changed(self, scale: Gtk.Scale) -> None:
        """Coalesce rapid scale drags into a single write."""
        if self._scale_source_id is not None:
            GLib.source_remove(self._scale_source_id)
        self._scale_source_id = GLib.timeout_add(self.SCALE_DEBOUNCE_MS, self._flush_scale)

    def _flush_scale(self) -> bool:
        """Emit the pending scale write once.  Returns False to drop the source."""
        self._scale_source_id = None
        scale = getattr(self, "control", None)
        if not isinstance(scale, Gtk.Scale):
            return False
        self._emit_set(int(round(scale.get_value())))
        return False


_RESEARCH_PENDING_FALLBACK = (
    "Linux Bluetooth protocol and health semantics are not yet validated. "
    "No hardware controls or mock telemetry are enabled until research completes."
)
_VALIDATED_FALLBACK = (
    "Frost Bay capability is locally validated. Runtime connection and health "
    "state are reported separately by the backend and are not implied by this card."
)


class FrostBayResearchCard(Gtk.Box):
    """Card rendering Frost Bay validation state from a CapabilityRecord.

    Validation state and runtime connection/health state are separate concepts.
    A future ``CONFIRMED_LOCAL`` Frost Bay record must not be presented as
    "Connected", and the pre-research "protocol not validated" wording must not
    leak onto a validated capability.
    """

    def __init__(self, record_telemetry: Optional[CapabilityRecord] = None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.add_css_class("card")
        self.set_margin_top(6)
        self.set_margin_bottom(6)
        self.set_margin_start(12)
        self.set_margin_end(12)

        # Header row
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

        if record_telemetry is None:
            sub_label = "Status: Unknown"
            status = CapabilityStatus.UNAVAILABLE
            desc_text = "No Frost Bay telemetry capability record provided by backend."
        else:
            status = record_telemetry.status
            if status == CapabilityStatus.RESEARCH_PENDING:
                sub_label = "Research Pending • Writes Blocked"
            elif status == CapabilityStatus.CONFIRMED_LOCAL:
                sub_label = "Locally Validated"
            else:
                sub_label = f"Status: {status.value}"

            desc_text = record_telemetry.reason_unavailable or _default_desc(status)

        status_label = Gtk.Label(label=sub_label)
        status_label.add_css_class("dim-label")
        status_label.add_css_class("caption")
        status_label.set_xalign(0.0)
        title_box.append(status_label)
        header.append(title_box)

        header.append(StatusBadge(status))
        self.append(header)

        # Description text
        desc = Gtk.Label(label=desc_text)
        desc.set_wrap(True)
        desc.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
        desc.set_xalign(0.0)
        desc.add_css_class("dim-label")
        self.append(desc)

        # Render any warnings present in record
        if record_telemetry and record_telemetry.warnings:
            for warn in record_telemetry.warnings:
                self.append(SafetyBanner(warn, record_telemetry.safety_state))


def _default_desc(status: CapabilityStatus) -> str:
    if status == CapabilityStatus.RESEARCH_PENDING:
        return _RESEARCH_PENDING_FALLBACK
    if status == CapabilityStatus.CONFIRMED_LOCAL:
        return _VALIDATED_FALLBACK
    return ""


class MiniSsdStatusCard(Gtk.Box):
    """Card dynamically deriving Mini SSD presence and reliability from CapabilityRecords."""

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

        if presence is None or presence.observed_value is None:
            state_str = "State: Unknown"
            presence_status = presence.status if presence else CapabilityStatus.UNAVAILABLE
        else:
            state_str = f"State: {format_observed_value(presence)}"
            presence_status = presence.status

        state_label = Gtk.Label(label=state_str)
        state_label.add_css_class("dim-label")
        state_label.add_css_class("caption")
        state_label.set_xalign(0.0)
        title_box.append(state_label)
        header.append(title_box)

        header.append(StatusBadge(presence_status))
        self.append(header)

        # Derive reliability banner
        if reliability is None:
            self.append(SafetyBanner("Reliability: Unknown", SafetyState.UNKNOWN))
        else:
            rel_val = reliability.observed_value or reliability.safety_state.value
            rel_header = f"Reliability: {rel_val}"
            if reliability.warnings:
                msg = rel_header + "\n" + "\n".join(reliability.warnings)
            elif reliability.reason_unavailable:
                msg = rel_header + "\n" + reliability.reason_unavailable
            else:
                msg = rel_header

            self.append(SafetyBanner(msg, reliability.safety_state))
