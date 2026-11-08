"""Profile persistence and transactions use only fake clients and temporary files."""
from dataclasses import replace
import os
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from superx_helper.contracts import CapabilityRecord, CapabilitySnapshot, CapabilityStatus, OperationResult
from superx_helper.profiles import (
    DEFAULT_PROFILES, Profile, apply_profile, load_profiles, load_selected_profile,
    profile_steps, save_profiles, save_selected_profile,
)


def record(cid, value, writable=True):
    return CapabilityRecord(cid, cid, CapabilityStatus.CONFIRMED_LOCAL,
                            True, True, True, observed_value=value,
                            write_authorized=writable,
                            allowed_values=["power-saver", "balanced", "performance"] if cid == "performance.epp" else [],
                            minimum=5 if cid == "display.brightness" else None,
                            maximum=100 if cid == "display.brightness" else None)


class FakeClient:
    def __init__(self):
        self.records = [record("performance.epp", "balanced"), record("display.brightness", 70)]
        self.calls = []
        self.fail_at = None
        self.mismatch_at = None
        self.raise_at = None
        self.revoke_at = None
        self.dry_run_at = None

    def get_snapshot(self):
        return CapabilitySnapshot(1, "test", list(self.records))

    def set_capability(self, cid, value):
        current = self.get_snapshot().by_id(cid)
        assert current is not None and current.can_write, "unauthorized write"
        self.calls.append((cid, value))
        count = len(self.calls)
        if count != self.mismatch_at:
            self.records = [replace(r, observed_value=value) if r.capability_id == cid else r for r in self.records]
        if count == self.revoke_at:
            self.records = [replace(r, write_authorized=False) for r in self.records]
        if count == self.raise_at:
            raise RuntimeError("owner lost after mutation")
        return OperationResult(count != self.fail_at, cid, value, error_message="forced failure" if count == self.fail_at else None,
                               dry_run=count == self.dry_run_at)


class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        env = patch.dict(os.environ, {"XDG_CONFIG_HOME": self.temp.name})
        env.start()
        self.addCleanup(env.stop)

    def test_round_trip_and_separate_selection(self):
        profiles = [Profile("Custom", "An ordinary description.", "balanced", 50, "auto", 45)]
        save_profiles(profiles)
        path = Path(self.temp.name) / "superx-helper" / "profiles.yaml"
        before = path.read_bytes()
        save_selected_profile("Custom")
        self.assertEqual(load_profiles(), profiles)
        self.assertEqual(load_selected_profile(), "Custom")
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(sorted(p.name for p in path.parent.iterdir()), ["profile-state.yaml", "profiles.yaml"])

    def test_missing_defaults(self):
        self.assertEqual(load_profiles(), list(DEFAULT_PROFILES))
        self.assertIsNone(load_selected_profile())

    def test_corrupt_fallback_warns(self):
        path = Path(self.temp.name) / "superx-helper" / "profiles.yaml"
        path.parent.mkdir()
        for data in ("[broken", "!!python/object:evil {}", "{}", "- name: invalid\n  description: test\n  extra: true", "- name: Bad\n  description: test\n  brightness: true"):
            with self.subTest(data=data):
                path.write_text(data)
                with self.assertLogs("superx_helper.profiles", level="WARNING"):
                    self.assertEqual(load_profiles(), list(DEFAULT_PROFILES))
                self.assertEqual(path.read_text(), data)

    def test_atomic_failure_preserves_definitions(self):
        save_profiles(list(DEFAULT_PROFILES))
        path = Path(self.temp.name) / "superx-helper" / "profiles.yaml"
        before = path.read_bytes()
        with patch("superx_helper.profiles.os.replace", side_effect=OSError("disk error")):
            with self.assertRaises(OSError):
                save_profiles([Profile("Other", "Description")])
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual([p.name for p in path.parent.iterdir()], ["profiles.yaml"])

    def test_recursive_yaml_falls_back_in_both_loaders(self):
        path = Path(self.temp.name) / "superx-helper"
        path.mkdir()
        data = "[" * 1000 + "0" + "]" * 1000
        for filename, loader, fallback in (
            ("profiles.yaml", load_profiles, list(DEFAULT_PROFILES)),
            ("profile-state.yaml", load_selected_profile, None),
        ):
            with self.subTest(filename=filename):
                (path / filename).write_text(data)
                with self.assertLogs("superx_helper.profiles", level="WARNING"):
                    self.assertEqual(loader(), fallback)

    def test_duplicate_names_rejected(self):
        with self.assertRaises(ValueError):
            save_profiles([DEFAULT_PROFILES[0], DEFAULT_PROFILES[0]])


class ValidationTests(unittest.TestCase):
    def test_rejects_paths_commands_and_controls(self):
        for bad in ("/tmp/config", "../file", "C:\\Windows", "$(id)", "echo test; reboot", "sudo reboot", "bash command", "echo hello", "reboot", "a|b", "x\ny", "<b>Text</b>", "\x00", "https://example.com"):
            for key in ("name", "description", "epp", "internal_fan_mode"):
                with self.subTest(key=key, bad=bad), self.assertRaises(ValueError):
                    Profile.from_dict({"name": "Test", "description": "Description", key: bad})

    def test_numeric_boundaries(self):
        for key, bad_values in (("brightness", (True, False, 4, 101, 5.5, "50", float("nan"))),
                                ("power_target_w", (True, False, 0, -1, 1001, 45.5, "45", float("inf")))):
            for value in bad_values:
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    Profile.from_dict({"name": "Test", "description": "Description", key: value})
        for brightness in (5, 100):
            self.assertEqual(Profile("Test", "Description", brightness=brightness).brightness, brightness)

    def test_unknown_keys_types_and_requirements(self):
        for data in ({"name": "Test", "description": "Description", "command": "foo"},
                     {"name": True, "description": "Description"}, {}, [],
                     {"name": "Test", "description": "Description", "requires": {"unknown": "healthy"}},
                     {"name": "Test", "description": "Description", "requires": {"frost_bay_health": "sudo reboot"}},
                     {"name": "Test", "description": "Description", "epp": "balance_performance"}):
            with self.subTest(data=data), self.assertRaises(ValueError):
                Profile.from_dict(data)


class ApplyTests(unittest.TestCase):
    def setUp(self):
        self.client = FakeClient()
        self.profile = Profile("Test", "Description", "power-saver", 50)

    def test_success_verifies_fresh_observed_state(self):
        result = apply_profile(self.client, self.profile)
        self.assertTrue(result.success)
        self.assertEqual([s.status for s in result.steps], ["applied", "applied"])
        self.assertFalse(result.rollback_attempted)
        self.assertEqual(self.client.get_snapshot().by_id("display.brightness").observed_value, 50)

    def test_nonwritable_and_future_fields_never_write(self):
        self.client.records = [replace(r, write_authorized=False) for r in self.client.records]
        self.client.records += [record("cooling.internal_fan", 50), record("performance.power_target", 45)]
        result = apply_profile(self.client, replace(self.profile, internal_fan_mode="auto", power_target_w=45))
        self.assertFalse(result.success)
        self.assertEqual(self.client.calls, [])
        self.assertTrue(all(s.status == "skipped" and s.reason for s in result.steps))

    def test_missing_record_skipped(self):
        self.client.records = []
        result = apply_profile(self.client, self.profile)
        self.assertEqual(self.client.calls, [])
        self.assertTrue(all("missing" in s.reason for s in result.steps))

    def test_frost_bay_requirement_blocks_even_writable_fields(self):
        result = apply_profile(self.client, DEFAULT_PROFILES[-1])
        self.assertEqual(self.client.calls, [])
        self.assertIn("Frost Bay", result.steps[0].reason)

    def test_failure_second_step_restores_in_reverse_order(self):
        self.client.fail_at = 2
        result = apply_profile(self.client, self.profile)
        self.assertFalse(result.success)
        self.assertTrue(result.rollback_attempted)
        self.assertTrue(result.rollback_succeeded)
        self.assertEqual([s.rollback_status for s in result.steps], ["restored", "restored"])
        self.assertEqual(result.steps[1].status, "failed")
        self.assertEqual(self.client.calls, [("performance.epp", "power-saver"), ("display.brightness", 50),
                                             ("display.brightness", 70), ("performance.epp", "balanced")])

    def test_readback_mismatch_is_failure(self):
        self.client.mismatch_at = 2
        result = apply_profile(self.client, self.profile)
        self.assertFalse(result.success)
        self.assertIn("read-back", result.steps[1].reason)
        self.assertTrue(result.rollback_succeeded)

    def test_exception_after_mutation_restored(self):
        self.client.raise_at = 2
        result = apply_profile(self.client, self.profile)
        self.assertFalse(result.success)
        self.assertTrue(result.rollback_succeeded)

    def test_rollback_failure_reported_and_remaining_restore_attempted(self):
        self.client.fail_at = 2
        self.client.raise_at = 3
        result = apply_profile(self.client, self.profile)
        self.assertFalse(result.rollback_succeeded)
        self.assertEqual(result.steps[1].rollback_status, "failed")
        self.assertEqual(result.steps[0].rollback_status, "restored")

    def test_revoked_authorization_never_written_during_rollback(self):
        self.client.fail_at = self.client.revoke_at = 2
        result = apply_profile(self.client, self.profile)
        self.assertFalse(result.rollback_succeeded)
        self.assertEqual(len(self.client.calls), 2)

    def test_unknown_or_unrestorable_observed_value_skipped(self):
        for value in (None, True, 0, 4):
            self.client = FakeClient()
            self.client.records[1] = replace(self.client.records[1], observed_value=value)
            result = apply_profile(self.client, self.profile)
            self.assertEqual(len(self.client.calls), 1)
            self.assertIn("restorable", result.steps[1].reason)

    def test_host_options_gate(self):
        self.client.records[0] = replace(self.client.records[0], allowed_values=["balanced"])
        result = apply_profile(self.client, self.profile)
        self.assertEqual(self.client.calls, [("display.brightness", 50)])
        self.assertIn("advertised", result.steps[0].reason)

    def test_snapshot_exception_reported(self):
        with patch.object(self.client, "get_snapshot", side_effect=RuntimeError("snapshot lost")):
            result = apply_profile(self.client, self.profile)
        self.assertFalse(result.success)
        self.assertEqual(result.error_message, "snapshot lost")
        self.assertEqual(self.client.calls, [])

    def test_dry_run_not_success(self):
        self.client.dry_run_at = 1
        result = apply_profile(self.client, self.profile)
        self.assertFalse(result.success)
        self.assertTrue(result.rollback_succeeded)
        self.assertEqual(result.steps[1].status, "skipped")


class ProfileAsyncTests(unittest.TestCase):
    """Exercise the page callbacks without constructing GTK widgets or a bus."""

    def setUp(self):
        from gi.repository import Gio
        guard = patch.object(Gio, "bus_get_sync", side_effect=AssertionError("real bus"))
        guard.start()
        self.addCleanup(guard.stop)

    def page(self, client):
        from superx_helper.ui.pages.profiles import ProfilesPage
        page = SimpleNamespace(
            busy=False, client=client, selected=0,
            profiles=[Profile("Test", "Description", "power-saver", 50)],
            _render=Mock(), result_label=Mock(), get_root=lambda: None,
            on_refresh=Mock(), update_from_snapshot=Mock(),
        )
        page._finished = lambda result: ProfilesPage._finished(page, result)
        return page

    def test_profile_rollback_finishes_before_ordinary_write(self):
        from superx_helper.client import apply_capability_async, submit_serial
        from superx_helper.ui.pages.profiles import ProfilesPage
        client = FakeClient()
        client.fail_at = 2
        entered, release = threading.Event(), threading.Event()
        ordinary_executed = threading.Event()
        original_set = client.set_capability

        def blocked_set(cid, value):
            if cid == "display.brightness" and value == 50:
                entered.set()
                if not release.wait(2):
                    raise RuntimeError("test did not release profile")
            if value == "performance":
                ordinary_executed.set()
            return original_set(cid, value)

        client.set_capability = blocked_set
        page = self.page(client)
        callbacks = []
        queued = []

        def submit(work):
            future = submit_serial(work)
            queued.append(future)
            return future

        with patch("superx_helper.ui.pages.profiles.Gio.Application.get_default", return_value=None), \
                patch("superx_helper.ui.pages.profiles.submit_serial", side_effect=submit), \
                patch("superx_helper.client.GLib.idle_add", side_effect=lambda *args: callbacks.append(args)):
            try:
                ProfilesPage._apply(page, None)
                self.assertTrue(entered.wait(1))
                ordinary = apply_capability_async(client, "performance.epp", "performance", Mock())
                self.assertFalse(ordinary_executed.wait(0.05))
            finally:
                release.set()
                for future in queued:
                    future.result(timeout=2)
            ordinary.result(timeout=2)
        self.assertEqual(client.calls, [
            ("performance.epp", "power-saver"), ("display.brightness", 50),
            ("display.brightness", 70), ("performance.epp", "balanced"),
            ("performance.epp", "performance"),
        ])
        self.assertEqual(client.get_snapshot().by_id("performance.epp").observed_value, "performance")
        with self.assertLogs("superx_helper.ui.pages.profiles", level="WARNING"):
            callbacks[0][0](*callbacks[0][1:])

    def test_application_hold_released_on_main_loop_even_without_root(self):
        from superx_helper.client import submit_serial
        from superx_helper.ui.pages.profiles import ProfilesPage
        for outcome in ("success", "rollback", "exception", "submission failure"):
            with self.subTest(outcome=outcome):
                client = FakeClient()
                if outcome == "rollback":
                    client.fail_at = 2
                page = self.page(client)
                application = SimpleNamespace(holds=0)
                main_thread = threading.get_ident()
                threads = []

                def hold():
                    self.assertEqual(threading.get_ident(), main_thread)
                    application.holds += 1

                def release():
                    self.assertEqual(threading.get_ident(), main_thread)
                    application.holds -= 1

                application.hold, application.release = Mock(side_effect=hold), Mock(side_effect=release)
                callbacks, futures = [], []

                def submit(work):
                    if outcome == "submission failure":
                        raise RuntimeError("executor stopped")
                    future = submit_serial(work)
                    futures.append(future)
                    return future

                def apply(fake, profile):
                    threads.append(threading.current_thread().name)
                    if outcome == "exception":
                        raise RuntimeError("unexpected failure")
                    return apply_profile(fake, profile)

                with patch("superx_helper.ui.pages.profiles.Gio.Application.get_default", return_value=application), \
                        patch("superx_helper.ui.pages.profiles.submit_serial", side_effect=submit), \
                        patch("superx_helper.ui.pages.profiles.apply_profile", side_effect=apply), \
                        patch("superx_helper.ui.pages.profiles.GLib.idle_add", side_effect=lambda *args: callbacks.append(args)), \
                        self.assertLogs("superx_helper.ui.pages.profiles", level="INFO") as logs:
                    ProfilesPage._apply(page, None)
                    for future in futures:
                        future.result(timeout=2)
                    if futures:
                        self.assertEqual(application.holds, 1)
                        self.assertTrue(threads[0].startswith("superx-apply"))
                        self.assertEqual(len(callbacks), 1)
                        callback, result = callbacks[0]
                        if outcome == "rollback":
                            self.assertTrue(result.rollback_succeeded)
                        callback(result)
                application.hold.assert_called_once()
                application.release.assert_called_once()
                self.assertEqual(application.holds, 0)
                self.assertFalse(page.busy)
                page.result_label.set_text.assert_called_once_with("Applying profile…")
                page._render.assert_called_once()
                page.on_refresh.assert_not_called()
                self.assertIn("Profile applied." if outcome == "success" else "Profile was not applied.", logs.output[0])


class ProfileUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from gi.repository import Adw
        Adw.init()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        env = patch.dict(os.environ, {"XDG_CONFIG_HOME": self.temp.name})
        env.start()
        self.addCleanup(env.stop)

    def test_live_inert_text_and_apply_sensitivity(self):
        from superx_helper.ui.pages.profiles import ProfilesPage
        from test_ui_widgets import collect_row_subtitles
        save_profiles([replace(DEFAULT_PROFILES[1], brightness=50, internal_fan_mode="auto"), DEFAULT_PROFILES[-1]])
        page = ProfilesPage()
        client = FakeClient()
        page.set_client(client)
        page.update_from_snapshot(client.get_snapshot())
        text = " ".join(collect_row_subtitles(page))
        self.assertIn("epp: balanced — Will apply", text)
        self.assertIn("brightness: 50 — Will apply", text)
        self.assertIn("Inert: Declared future field", text)
        self.assertIn("Frost Bay health is not qualified", text)
        self.assertIn("power-increasing", text)
        self.assertFalse(page.apply_button.get_sensitive())  # Liquid selected
        page.selected = 0
        page.update_from_snapshot(client.get_snapshot())
        self.assertTrue(page.apply_button.get_sensitive())
        self.assertEqual(client.calls, [])

    def test_apply_runs_on_worker_and_completion_on_idle(self):
        from superx_helper.ui.pages.profiles import ProfilesPage
        page = ProfilesPage()
        client = FakeClient()
        page.set_client(client)
        page.update_from_snapshot(client.get_snapshot())
        done = threading.Event()
        callbacks = []
        thread_ids = []

        def apply(fake, profile):
            thread_ids.append(threading.get_ident())
            return apply_profile(fake, profile)

        def idle(callback, result):
            callbacks.append((callback, result))
            done.set()

        with patch("superx_helper.ui.pages.profiles.apply_profile", side_effect=apply), patch("superx_helper.ui.pages.profiles.GLib.idle_add", side_effect=idle):
            page._apply(None)
            self.assertTrue(done.wait(2))
        self.assertNotEqual(thread_ids, [threading.get_ident()])
        self.assertTrue(page.busy)
        with patch.object(page, "get_root", return_value=Mock()):
            callbacks[0][0](callbacks[0][1])
        self.assertFalse(page.busy)
        self.assertIn("applied", page.result_label.get_text())


if __name__ == "__main__":
    unittest.main()
