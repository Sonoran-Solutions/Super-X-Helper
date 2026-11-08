"""Declarative profile editor and verified application through ServiceClient."""
from __future__ import annotations

from dataclasses import replace
import threading
from typing import Callable

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk

from superx_helper.client import ServiceClient
from superx_helper.contracts import CapabilitySnapshot
from superx_helper.profiles import (
    EPP_VALUES, ProfileApplyResult, apply_profile, load_profiles,
    load_selected_profile, profile_steps, save_profiles, save_selected_profile,
)
from superx_helper.ui.pages.base import BasePage
from superx_helper.ui_manifest import PageSpec


class ProfilesPage(BasePage):
    def __init__(self, spec: PageSpec | None = None):
        super().__init__(spec or PageSpec("profiles", "Profiles", []))
        self.profiles = load_profiles()
        selected = load_selected_profile()
        self.selected = next((i for i, p in enumerate(self.profiles) if p.name == selected), 1 if len(self.profiles) > 1 else 0)
        self.client = None
        self.on_refresh = None
        self.snapshot = None
        self.busy = False
        self.profiles_group = Adw.PreferencesGroup(title="Available Profiles")
        self.add(self.profiles_group)
        self.editor_group = Adw.PreferencesGroup(title="Selected Profile")
        self.add(self.editor_group)
        self.result_label = Gtk.Label(wrap=True, xalign=0, selectable=True)
        self.warnings_group.add(self.result_label)
        self._render()

    def set_client(self, client: ServiceClient, on_refresh: Callable[[], None] | None = None) -> None:
        self.client = client
        self.on_refresh = on_refresh
        self._render()

    def update_from_snapshot(self, snapshot: CapabilitySnapshot) -> None:
        self.snapshot = snapshot
        self._render()

    def _render(self) -> None:
        self.remove(self.profiles_group)
        self.profiles_group = Adw.PreferencesGroup(title="Available Profiles")
        self.add(self.profiles_group)
        radio_group = None
        for index, profile in enumerate(self.profiles):
            lines = [profile.description]
            steps = profile_steps(profile, self.snapshot) if self.snapshot else []
            for step in steps:
                value = str(step.requested_value)
                if step.field == "epp" and value == "performance":
                    value += " (power-increasing; not exercised live)"
                lines.append(f"{step.field}: {value} — " + (f"Inert: {step.reason}" if step.reason else "Will apply"))
            row = Adw.ActionRow(title=profile.name, subtitle="\n".join(lines))
            row.set_use_markup(False)
            radio = Gtk.CheckButton()
            if radio_group is not None:
                radio.set_group(radio_group)
            else:
                radio_group = radio
            radio.set_active(index == self.selected)
            radio.set_sensitive(not self.busy)
            radio.set_tooltip_text("Select " + profile.name)
            radio.connect("toggled", self._select, index)
            row.add_suffix(radio)
            self.profiles_group.add(row)

        self.remove(self.editor_group)
        self.editor_group = Adw.PreferencesGroup(title="Selected Profile")
        self.add(self.editor_group)
        if self.snapshot is None:
            return
        profile = self.profiles[self.selected]
        epp_row = Adw.ActionRow(title="Power profile", subtitle="Performance is power-increasing; not exercised live")
        self.epp_editor = Gtk.DropDown.new_from_strings(["Unspecified", "power-saver", "balanced", "performance (power-increasing)"])
        self.epp_editor.set_selected(EPP_VALUES.index(profile.epp) + 1 if profile.epp else 0)
        epp_row.add_suffix(self.epp_editor)
        self.editor_group.add(epp_row)
        bright_row = Adw.ActionRow(title="Brightness", subtitle="Percent from 5 to 100; enable to include in profile")
        self.brightness_enabled = Gtk.CheckButton(active=profile.brightness is not None)
        self.brightness_editor = Gtk.SpinButton.new_with_range(5, 100, 1)
        self.brightness_editor.set_value(profile.brightness if profile.brightness is not None else 50)
        bright_row.add_suffix(self.brightness_enabled)
        bright_row.add_suffix(self.brightness_editor)
        self.editor_group.add(bright_row)
        save = Gtk.Button(label="Save edits")
        save.connect("clicked", self._save)
        self.editor_group.add(save)
        self.apply_button = Gtk.Button(label="Apply saved profile")
        self.apply_button.connect("clicked", self._apply)
        self.editor_group.add(self.apply_button)
        self.editor_group.set_sensitive(not self.busy)
        self.apply_button.set_sensitive(not self.busy and self.client is not None and any(
            step.status == "ready" for step in profile_steps(profile, self.snapshot)
        ))

    def _select(self, radio: Gtk.CheckButton, index: int) -> None:
        if not radio.get_active() or index == self.selected:
            return
        self.selected = index
        try:
            save_selected_profile(self.profiles[index].name)
        except OSError as exc:
            self.result_label.set_text(f"Selection could not be saved: {exc}")
        self._render()

    def _save(self, _button) -> None:
        try:
            selected = self.epp_editor.get_selected()
            profile = replace(self.profiles[self.selected],
                              epp=EPP_VALUES[selected - 1] if selected else None,
                              brightness=self.brightness_editor.get_value_as_int() if self.brightness_enabled.get_active() else None)
            profiles = list(self.profiles)
            profiles[self.selected] = profile
            save_profiles(profiles)
            self.profiles = profiles
            self.result_label.set_text("Profile definitions saved. Apply explicitly to change hardware state.")
            self._render()
        except (OSError, ValueError) as exc:
            self.result_label.set_text(f"Profile could not be saved: {exc}")

    def _apply(self, _button) -> None:
        if self.busy or self.client is None:
            return
        self.busy = True
        profile, client = self.profiles[self.selected], self.client
        self._render()
        self.result_label.set_text("Applying profile…")

        def work():
            result = apply_profile(client, profile)
            GLib.idle_add(self._finished, result)

        threading.Thread(target=work, daemon=True, name="profile-apply").start()

    def _finished(self, result: ProfileApplyResult) -> bool:
        self.busy = False
        lines = ["Profile applied." if result.success else "Profile was not applied."]
        if result.error_message:
            lines.append(result.error_message)
        for step in result.steps:
            text = f"{step.field}: {step.status}"
            if step.reason:
                text += f" — {step.reason}"
            if step.rollback_status:
                text += f"; rollback {step.rollback_status} {step.rollback_reason}"
            lines.append(text)
        if result.rollback_attempted:
            lines.append("Rollback fully verified." if result.rollback_succeeded else "Rollback incomplete; check observed state.")
        self.result_label.set_text("\n".join(lines))
        try:
            if self.on_refresh:
                self.on_refresh()
            elif self.client:
                self.update_from_snapshot(self.client.get_snapshot())
        except Exception as exc:
            self.result_label.set_text("\n".join(lines) + f"\nRefresh failed: {exc}")
        self._render()
        return GLib.SOURCE_REMOVE
