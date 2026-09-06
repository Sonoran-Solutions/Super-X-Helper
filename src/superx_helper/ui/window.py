"""Main application window for Super X Helper."""

from __future__ import annotations

from typing import Dict, Optional

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

from superx_helper.client import ServiceClient
from superx_helper.contracts import CapabilitySnapshot
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
from superx_helper.ui.widgets import SafetyBanner
from superx_helper.ui_manifest import PAGES, PageSpec

PAGE_ICONS = {
    "dashboard": "view-grid-symbolic",
    "performance": "utilities-system-monitor-symbolic",
    "cooling": "weather-snow-symbolic",
    "display": "video-display-symbolic",
    "power": "battery-symbolic",
    "storage": "drive-harddisk-symbolic",
    "profiles": "preferences-system-symbolic",
    "diagnostics": "system-search-symbolic",
}


class SuperXWindow(Adw.ApplicationWindow):
    """Main window hosting navigation and capability-driven pages."""

    def __init__(self, app: Adw.Application, client: ServiceClient):
        super().__init__(application=app)
        self.client = client
        self.set_title("Super X Helper")
        self.set_default_size(960, 680)

        # Page instances mapping
        self.pages: Dict[str, BasePage] = {}

        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        # Main vertical layout inside a ToolbarView
        self.toolbar_view = Adw.ToolbarView()
        self.set_content(self.toolbar_view)

        # Header bar
        self.header_bar = Adw.HeaderBar()
        title_widget = Adw.WindowTitle(
            title="Super X Helper",
            subtitle="ONEXPLAYER Super X • Linux Control Center",
        )
        self.header_bar.set_title_widget(title_widget)

        # Refresh button
        refresh_btn = Gtk.Button.new_from_icon_name("view-refresh-symbolic")
        refresh_btn.set_tooltip_text("Refresh system capabilities and telemetry")
        refresh_btn.connect("clicked", lambda _: self.refresh())
        self.header_bar.pack_end(refresh_btn)

        self.toolbar_view.add_top_bar(self.header_bar)

        # Split container: Sidebar on left, ViewStack on right
        split_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)

        # Sidebar navigation
        sidebar_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        sidebar_box.set_size_request(220, -1)
        sidebar_box.add_css_class("sidebar")
        sidebar_box.set_margin_top(8)
        sidebar_box.set_margin_bottom(8)
        sidebar_box.set_margin_start(8)
        sidebar_box.set_margin_end(4)

        sidebar_scroll = Gtk.ScrolledWindow()
        sidebar_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sidebar_scroll.set_vexpand(True)

        self.nav_list = Gtk.ListBox()
        self.nav_list.add_css_class("navigation-sidebar")
        self.nav_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.nav_list.connect("row-selected", self._on_nav_selected)

        sidebar_scroll.set_child(self.nav_list)
        sidebar_box.append(sidebar_scroll)
        split_box.append(sidebar_box)

        # Content area with ViewStack
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        content_box.set_hexpand(True)
        content_box.set_vexpand(True)

        self.view_stack = Adw.ViewStack()
        content_box.append(self.view_stack)
        split_box.append(content_box)

        self.toolbar_view.set_content(split_box)

        # Instantiate pages defined in ui_manifest.PAGES
        first_row = None
        for spec in PAGES:
            page = self._create_page_instance(spec)
            self.pages[spec.page_id] = page
            self.view_stack.add_titled(page, spec.page_id, spec.title)

            # Create sidebar row
            row = Gtk.ListBoxRow()
            row_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            row_box.set_margin_top(6)
            row_box.set_margin_bottom(6)
            row_box.set_margin_start(8)
            row_box.set_margin_end(8)

            icon_name = PAGE_ICONS.get(spec.page_id, "application-x-executable-symbolic")
            img = Gtk.Image.new_from_icon_name(icon_name)
            row_box.append(img)

            label = Gtk.Label(label=spec.title)
            label.set_xalign(0.0)
            row_box.append(label)

            row.set_child(row_box)
            row.page_id = spec.page_id
            self.nav_list.append(row)

            if first_row is None:
                first_row = row

        if first_row:
            self.nav_list.select_row(first_row)

    def _create_page_instance(self, spec: PageSpec) -> BasePage:
        page_id = spec.page_id
        if page_id == "dashboard":
            return DashboardPage(spec)
        elif page_id == "performance":
            return PerformancePage(spec)
        elif page_id == "cooling":
            return CoolingPage(spec)
        elif page_id == "display":
            return DisplayPage(spec)
        elif page_id == "power":
            return PowerPage(spec)
        elif page_id == "storage":
            return StoragePage(spec)
        elif page_id == "profiles":
            return ProfilesPage(spec)
        elif page_id == "diagnostics":
            return DiagnosticsPage(spec)
        return BasePage(spec)

    def _on_nav_selected(self, listbox: Gtk.ListBox, row: Optional[Gtk.ListBoxRow]) -> None:
        if row and hasattr(row, "page_id"):
            self.view_stack.set_visible_child_name(row.page_id)

    def refresh(self) -> None:
        """Fetch fresh capability snapshot and update all pages."""
        snapshot = self.client.get_snapshot()
        for page in self.pages.values():
            if hasattr(page, "update_from_snapshot"):
                page.update_from_snapshot(snapshot)
