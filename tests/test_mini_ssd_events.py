"""Recorded-text tests for cross-boot Mini SSD kernel event capture.

No hardware, journalctl, or other external command is executed: a fake runner
serves the recorded fixtures under ``tests/fixtures/mini_ssd_journal``.
"""

import json
from pathlib import Path
import unittest
from typing import Dict, Sequence, Tuple

from superx_helper.collector import (
    MINI_SSD_PCI_ADDRESS,
    format_summary,
    get_mini_ssd_boot_events,
    parse_mini_ssd_boot_log,
)

FIXTURES = Path(__file__).parent / "fixtures" / "mini_ssd_journal"

# boot_id -> recorded kernel text file name
BOOT_LOGS = {
    "aaaa1111bbbb2222cccc3333dddd4444": "boot_aaaa1111.kernel.txt",
    "edb0b6bc609540c997ba448ce65a6ee2": "boot_edb0b6bc.kernel.txt",
    "ffff5555eeee6666dddd7777cccc8888": "boot_ffff5555.kernel.txt",
}

SWAP_BOOT_ID = "aaaa1111bbbb2222cccc3333dddd4444"
LOSS_BOOT_ID = "edb0b6bc609540c997ba448ce65a6ee2"
QUIET_BOOT_ID = "ffff5555eeee6666dddd7777cccc8888"


def _read_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _list_boots_json() -> str:
    return _read_fixture("list_boots.json")


def fake_runner(argv: Sequence[str]) -> Tuple[int, str, str]:
    """Serve recorded text based on argv, mirroring journalctl's stdout."""

    argv = list(argv)
    if argv[:2] == ["journalctl", "--list-boots"]:
        return 0, _list_boots_json(), ""
    if argv[:2] == ["journalctl", "-k"] and "-b" in argv:
        boot_id = argv[argv.index("-b") + 1]
        fixture = BOOT_LOGS.get(boot_id)
        if fixture is None:
            return 1, "", f"no fixture for boot {boot_id}"
        return 0, _read_fixture(fixture), ""
    return 127, "", f"unexpected command: {argv}"


def failing_runner(argv: Sequence[str]) -> Tuple[int, str, str]:
    del argv
    return 1, "", "journalctl unavailable"


def _messages(boot: Dict[str, object]) -> list:
    return [event["message"] for event in boot["events"]]


class MiniSsdBootLogParserTests(unittest.TestCase):
    def test_loss_boot_events(self):
        parsed = parse_mini_ssd_boot_log(_read_fixture(BOOT_LOGS[LOSS_BOOT_ID]))

        self.assertEqual(parsed["controller"], "nvme0")
        self.assertEqual(parsed["suspend_count"], 1)

        messages = [event["message"] for event in parsed["events"]]
        self.assertEqual(
            messages,
            [
                "nvme nvme0: controller is down; will reset: CSTS=0xffffffff, PCI_STATUS=0x10",
                "nvme 0000:c4:00.0: enabling device (0000 -> 0002)",
                "nvme nvme0: Disabling device after reset failure: -19",
                "nvme 0000:c4:00.0: PM: failed to suspend async: error -16",
            ],
        )

        down, enabling, disabling, suspend_fail = parsed["events"]
        for event in (down, enabling, disabling):
            self.assertFalse(event["suspend_before"])
            self.assertEqual(event["suspends_before"], 0)
            self.assertEqual(event["controller"], "nvme0")
        self.assertTrue(suspend_fail["suspend_before"])
        self.assertEqual(suspend_fail["suspends_before"], 1)

        self.assertEqual(down["timestamp"], "2026-09-19T06:07:13-07:00")
        self.assertEqual(suspend_fail["timestamp"], "2026-09-19T16:11:53-07:00")

        for probe in (
            "pci function",
            "allocated 64 MiB host memory buffer",
            "16/0/0 default/read/poll queues",
            "using unchecked data buffer",
        ):
            self.assertFalse(any(probe in message for message in messages), probe)

    def test_controller_swap_boot(self):
        parsed = parse_mini_ssd_boot_log(_read_fixture(BOOT_LOGS[SWAP_BOOT_ID]))

        self.assertEqual(parsed["controller"], "nvme1")
        self.assertEqual(parsed["suspend_count"], 0)

        messages = [event["message"] for event in parsed["events"]]
        self.assertEqual(len(messages), 1)
        self.assertIn("nvme nvme1: I/O 21 QID 4 timeout, aborting", messages)
        self.assertFalse(any("nvme0" in message for message in messages))
        self.assertFalse(any("I/O 12 QID 3" in message for message in messages))
        self.assertEqual(parsed["events"][0]["controller"], "nvme1")

    def test_quiet_boot_has_no_events(self):
        parsed = parse_mini_ssd_boot_log(_read_fixture(BOOT_LOGS[QUIET_BOOT_ID]))

        self.assertEqual(parsed["events"], [])
        self.assertEqual(parsed["controller"], "nvme1")
        self.assertEqual(parsed["suspend_count"], 2)

    def test_serial_lines_and_hostname_never_kept(self):
        for fixture in BOOT_LOGS.values():
            parsed = parse_mini_ssd_boot_log(_read_fixture(fixture))
            dumped = json.dumps(parsed)
            self.assertNotIn("FAKESERIAL123", dumped)
            self.assertNotIn("subsysnqn", dumped)
            self.assertNotIn("nqn.", dumped)
            self.assertNotIn("superx", dumped)

    def test_reenumeration_uses_mapping_in_effect(self):
        text = "\n".join(
            [
                "2026-01-01T00:00:00+00:00 superx kernel: nvme nvme0: pci function 0000:c4:00.0",
                "2026-01-01T00:00:01+00:00 superx kernel: nvme nvme0: I/O 1 QID 1 timeout, aborting",
                "2026-01-01T00:00:02+00:00 superx kernel: nvme nvme2: pci function 0000:c4:00.0",
                "2026-01-01T00:00:03+00:00 superx kernel: nvme nvme0: I/O 2 QID 1 timeout, aborting",
                "2026-01-01T00:00:04+00:00 superx kernel: nvme nvme2: controller is down",
                "2026-01-01T00:00:05+00:00 superx kernel: blk_update_request: I/O error, dev nvme2n1, sector 123",
            ]
        )
        parsed = parse_mini_ssd_boot_log(text)

        self.assertEqual(parsed["controller"], "nvme0")
        self.assertEqual(
            [(event["controller"], event["message"]) for event in parsed["events"]],
            [
                ("nvme0", "nvme nvme0: I/O 1 QID 1 timeout, aborting"),
                ("nvme2", "nvme nvme2: controller is down"),
                ("nvme2", "blk_update_request: I/O error, dev nvme2n1, sector 123"),
            ],
        )

    def test_unknown_pci_address_yields_no_controller(self):
        parsed = parse_mini_ssd_boot_log(
            _read_fixture(BOOT_LOGS[LOSS_BOOT_ID]), pci_address="0000:99:00.0"
        )
        self.assertIsNone(parsed["controller"])
        self.assertEqual(parsed["events"], [])
        self.assertEqual(parsed["suspend_count"], 1)


class MiniSsdBootEventsTests(unittest.TestCase):
    def test_top_level_counts_and_starts(self):
        result = get_mini_ssd_boot_events(fake_runner)

        self.assertTrue(result["available"])
        self.assertEqual(result["pci_address"], MINI_SSD_PCI_ADDRESS)
        self.assertEqual(result["boot_count"], 3)
        self.assertEqual(result["boots_with_events"], 2)
        self.assertEqual(result["event_count"], 5)
        self.assertEqual(
            [boot["boot_id"] for boot in result["boots"]],
            list(BOOT_LOGS.keys()),
        )

        starts = [boot["start"] for boot in result["boots"]]
        self.assertEqual(starts[0], "2026-09-13T05:33:27+00:00")
        self.assertEqual(starts[1], "2026-09-12T01:56:07+00:00")
        self.assertEqual(starts[2], "2026-09-11T04:13:20+00:00")

    def test_per_boot_record_shape(self):
        result = get_mini_ssd_boot_events(fake_runner)
        by_id = {boot["boot_id"]: boot for boot in result["boots"]}

        loss = by_id[LOSS_BOOT_ID]
        self.assertTrue(loss["available"])
        self.assertEqual(loss["index"], -2)
        self.assertEqual(loss["controller"], "nvme0")
        self.assertEqual(loss["suspend_count"], 1)
        self.assertEqual(len(loss["events"]), 4)

        quiet = by_id[QUIET_BOOT_ID]
        self.assertEqual(quiet["events"], [])
        self.assertEqual(quiet["suspend_count"], 2)

        swap = by_id[SWAP_BOOT_ID]
        self.assertEqual(swap["controller"], "nvme1")
        self.assertEqual(_messages(swap), ["nvme nvme1: I/O 21 QID 4 timeout, aborting"])

    def test_serial_never_emitted(self):
        result = get_mini_ssd_boot_events(fake_runner)
        dumped = json.dumps(result)
        summary = format_summary({"mini_ssd_events": result})
        for forbidden in ("FAKESERIAL123", "subsysnqn", "nqn."):
            self.assertNotIn(forbidden, dumped)
            self.assertNotIn(forbidden, summary)

    def test_summary_block(self):
        result = get_mini_ssd_boot_events(fake_runner)
        summary = format_summary({"mini_ssd_events": result})
        lines = summary.splitlines()

        reliability_index = next(
            i for i, line in enumerate(lines) if line.startswith("Mini SSD Reliability:")
        )
        header = lines[reliability_index + 1]
        self.assertEqual(
            header,
            "Mini SSD Events  : 5 event(s) in 2 of 3 boot(s) (keyed by PCI 0000:c4:00.0)",
        )
        self.assertIn("   boot edb0b6bc (2026-09-12T01:56:07+00:00, nvme0, suspends before first event: 0)", lines)
        self.assertIn(
            "     2026-09-19T06:07:13-07:00 "
            "nvme nvme0: controller is down; will reset: CSTS=0xffffffff, PCI_STATUS=0x10",
            lines,
        )
        self.assertIn("   boot aaaa1111 (2026-09-13T05:33:27+00:00, nvme1, suspends before first event: 0)", lines)

    def test_summary_tolerates_missing_data(self):
        summary = format_summary({})
        self.assertIn("Mini SSD Events  : unavailable (", summary)

    def test_list_boots_failure(self):
        result = get_mini_ssd_boot_events(failing_runner)

        self.assertFalse(result["available"])
        self.assertEqual(result["boots"], [])
        self.assertEqual(result["pci_address"], MINI_SSD_PCI_ADDRESS)
        self.assertIn("journalctl unavailable", result["reason"])
        self.assertLessEqual(len(result["reason"]), 240)

        summary = format_summary({"mini_ssd_events": result})
        self.assertIn("Mini SSD Events  : unavailable (journalctl unavailable)", summary)

    def test_boot_log_failure_is_recorded(self):
        def partial_runner(argv: Sequence[str]) -> Tuple[int, str, str]:
            argv = list(argv)
            if argv[:2] == ["journalctl", "--list-boots"]:
                return 0, _list_boots_json(), ""
            if argv[:2] == ["journalctl", "-k"]:
                boot_id = argv[argv.index("-b") + 1]
                if boot_id == LOSS_BOOT_ID:
                    return 1, "", "boot gone"
            return fake_runner(argv)

        result = get_mini_ssd_boot_events(partial_runner)
        self.assertTrue(result["available"])
        by_id = {boot["boot_id"]: boot for boot in result["boots"]}
        self.assertFalse(by_id[LOSS_BOOT_ID]["available"])
        self.assertIn("boot gone", by_id[LOSS_BOOT_ID]["reason"])
        self.assertEqual(by_id[LOSS_BOOT_ID]["events"], [])
        self.assertEqual(result["boots_with_events"], 1)

    def test_invalid_json_is_unavailable(self):
        def bad_json_runner(argv: Sequence[str]) -> Tuple[int, str, str]:
            del argv
            return 0, "not json", ""

        result = get_mini_ssd_boot_events(bad_json_runner)
        self.assertFalse(result["available"])
        self.assertIn("invalid JSON", result["reason"])


if __name__ == "__main__":
    unittest.main()
