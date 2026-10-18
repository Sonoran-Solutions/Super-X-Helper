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
    "0829aa11bb22cc33dd44ee55ff667788": "boot_0829loss.kernel.txt",
    "1a2b3c4d5e6f708192a3b4c5d6e7f809": "boot_probefail.kernel.txt",
    "9f8e7d6c5b4a39281706f5e4d3c2b1a0": "boot_absent.kernel.txt",
    "aaaa1111bbbb2222cccc3333dddd4444": "boot_aaaa1111.kernel.txt",
    "edb0b6bc609540c997ba448ce65a6ee2": "boot_edb0b6bc.kernel.txt",
    "ffff5555eeee6666dddd7777cccc8888": "boot_ffff5555.kernel.txt",
}

BIG_LOSS_BOOT_ID = "0829aa11bb22cc33dd44ee55ff667788"
PROBE_FAIL_BOOT_ID = "1a2b3c4d5e6f708192a3b4c5d6e7f809"
ABSENT_BOOT_ID = "9f8e7d6c5b4a39281706f5e4d3c2b1a0"
SWAP_BOOT_ID = "aaaa1111bbbb2222cccc3333dddd4444"
LOSS_BOOT_ID = "edb0b6bc609540c997ba448ce65a6ee2"
QUIET_BOOT_ID = "ffff5555eeee6666dddd7777cccc8888"

KERNEL = "superx kernel:"


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

        self.assertEqual(down["timestamp"], "2026-09-19T13:07:13+00:00")
        self.assertEqual(suspend_fail["timestamp"], "2026-09-19T23:11:53+00:00")

        self.assertEqual(down["kind"], "loss")
        self.assertTrue(down["episode_start"])
        self.assertEqual(enabling["kind"], "recovery")
        self.assertFalse(enabling["episode_start"])
        self.assertEqual(disabling["kind"], "loss")
        self.assertFalse(disabling["episode_start"])
        self.assertEqual(suspend_fail["kind"], "aftermath")

        self.assertEqual(parsed["loss_episodes"], 1)
        self.assertTrue(parsed["pcie_enumerated"])
        self.assertTrue(parsed["nvme_probed"])
        for event in parsed["events"]:
            self.assertTrue(event["timestamp"].endswith("+00:00"), event["timestamp"])

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
        self.assertEqual(parsed["events"][0]["kind"], "other")

    def test_controller_nvme1_never_captures_nvme0_namespaces(self):
        text = "\n".join(
            [
                f"2026-01-01T00:00:00+00:00 {KERNEL} nvme nvme1: pci function 0000:c4:00.0",
                f"2026-01-01T00:00:01+00:00 {KERNEL} EXT4-fs (nvme1n1p1): Remounting filesystem read-only",
                f"2026-01-01T00:00:02+00:00 {KERNEL} EXT4-fs (nvme0n1p1): Remounting filesystem read-only",
                f"2026-01-01T00:00:03+00:00 {KERNEL} I/O error, dev nvme0n1p1, sector 1",
                f"2026-01-01T00:00:04+00:00 {KERNEL} I/O error, dev nvme10n1, sector 1",
                f"2026-01-01T00:00:05+00:00 {KERNEL} I/O error, dev nvme1n1p1, sector 1",
            ]
        )
        parsed = parse_mini_ssd_boot_log(text)

        self.assertEqual(parsed["controller"], "nvme1")
        self.assertEqual(
            [event["message"] for event in parsed["events"]],
            [
                "EXT4-fs (nvme1n1p1): Remounting filesystem read-only",
                "I/O error, dev nvme1n1p1, sector 1",
            ],
        )

    def test_partition_lines_are_captured(self):
        text = "\n".join(
            [
                f"2026-01-01T00:00:00+00:00 {KERNEL} nvme nvme0: pci function 0000:c4:00.0",
                f"2026-01-01T00:00:01+00:00 {KERNEL} Aborting journal on device nvme0n1p1-8.",
                f"2026-01-01T00:00:02+00:00 {KERNEL} EXT4-fs (nvme0n1p1): Remounting filesystem read-only",
                f"2026-01-01T00:00:03+00:00 {KERNEL} I/O error, dev nvme0n1, sector 5",
            ]
        )
        parsed = parse_mini_ssd_boot_log(text)

        self.assertEqual([event["kind"] for event in parsed["events"]], ["io_error"] * 3)

    def test_probe_failure_boot(self):
        parsed = parse_mini_ssd_boot_log(_read_fixture(BOOT_LOGS[PROBE_FAIL_BOOT_ID]))

        self.assertIsNone(parsed["controller"])
        self.assertTrue(parsed["pcie_enumerated"])
        self.assertFalse(parsed["nvme_probed"])
        self.assertEqual(len(parsed["events"]), 2)
        self.assertEqual([event["kind"] for event in parsed["events"]], ["loss", "loss"])
        self.assertEqual(parsed["loss_episodes"], 1)
        self.assertTrue(parsed["events"][0]["episode_start"])
        self.assertFalse(parsed["events"][1]["episode_start"])
        for event in parsed["events"]:
            self.assertIsNone(event["controller"])
            self.assertTrue(event["timestamp"].endswith("+00:00"))

    def test_absent_boot(self):
        parsed = parse_mini_ssd_boot_log(_read_fixture(BOOT_LOGS[ABSENT_BOOT_ID]))

        self.assertEqual(parsed["events"], [])
        self.assertIsNone(parsed["controller"])
        self.assertFalse(parsed["pcie_enumerated"])
        self.assertFalse(parsed["nvme_probed"])
        self.assertEqual(parsed["loss_episodes"], 0)
        self.assertEqual(parsed["suspend_count"], 1)

    def test_big_loss_boot(self):
        parsed = parse_mini_ssd_boot_log(_read_fixture(BOOT_LOGS[BIG_LOSS_BOOT_ID]))
        events = parsed["events"]
        messages = [event["message"] for event in events]

        self.assertEqual(parsed["controller"], "nvme0")
        self.assertEqual(parsed["loss_episodes"], 2)

        # Partitions are matched; another device's namespaces never are.
        self.assertIn("EXT4-fs (nvme0n1p1): Remounting filesystem read-only", messages)
        self.assertIn("Aborting journal on device nvme0n1p1-8.", messages)
        self.assertTrue(any("potential data loss!" in message for message in messages))
        self.assertIn("EXT4-fs (nvme0n1p1): This should not happen!! Data will be lost", messages)

        by_message = {}
        for event in events:
            by_message.setdefault(event["message"], event)

        self.assertEqual(by_message["EXT4-fs (nvme0n1p1): Remounting filesystem read-only"]["kind"], "io_error")
        self.assertEqual(by_message["Aborting journal on device nvme0n1p1-8."]["kind"], "io_error")
        self.assertEqual(
            by_message["EXT4-fs (nvme0n1p1): This should not happen!! Data will be lost"]["kind"],
            "io_error",
        )
        self.assertEqual(by_message["nvme 0000:c4:00.0: PM: failed to suspend async: error -16"]["kind"], "aftermath")

        first_down = events[0]
        self.assertEqual(first_down["kind"], "loss")
        self.assertTrue(first_down["episode_start"])
        self.assertEqual(first_down["suspends_before"], 0)
        self.assertTrue(first_down["message"].startswith("nvme nvme0: controller is down"))
        disabling = events[2]
        self.assertEqual(disabling["kind"], "loss")
        self.assertFalse(disabling["episode_start"])

        recovery = [event for event in events if event["timestamp"] == "2026-08-29T18:51:35+00:00"]
        self.assertEqual(len(recovery), 1)
        self.assertEqual(recovery[0]["kind"], "recovery")
        self.assertIn("enabling device", recovery[0]["message"])

        episode_starts = [event for event in events if event["episode_start"]]
        self.assertEqual(len(episode_starts), 2)
        self.assertTrue(all(event["kind"] == "loss" for event in episode_starts))

        for event in events:
            self.assertTrue(event["timestamp"].endswith("+00:00"), event["timestamp"])

    def test_unparsable_timestamp_kept_raw(self):
        text = f"not-a-timestamp {KERNEL} nvme nvme0: pci function 0000:c4:00.0"
        parsed = parse_mini_ssd_boot_log(text)
        self.assertEqual(parsed["events"], [])

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
        self.assertFalse(parsed["pcie_enumerated"])
        self.assertFalse(parsed["nvme_probed"])


class MiniSsdBootEventsTests(unittest.TestCase):
    def test_top_level_counts_and_starts(self):
        result = get_mini_ssd_boot_events(fake_runner)

        self.assertTrue(result["available"])
        self.assertEqual(result["pci_address"], MINI_SSD_PCI_ADDRESS)
        self.assertEqual(result["boot_count"], 6)
        self.assertEqual(result["boots_with_events"], 4)
        self.assertEqual(result["event_count"], 35)
        self.assertEqual(result["boots_with_losses"], 3)
        self.assertEqual(result["loss_episodes"], 4)
        self.assertEqual(
            result["loss_episodes"], sum(boot["loss_episodes"] for boot in result["boots"])
        )
        self.assertEqual(
            [boot["boot_id"] for boot in result["boots"]],
            list(BOOT_LOGS.keys()),
        )

        starts = [boot["start"] for boot in result["boots"]]
        self.assertEqual(starts[0], "2026-08-29T16:19:06+00:00")
        self.assertEqual(starts[1], "2026-10-01T15:00:01+00:00")
        self.assertEqual(starts[2], "2026-10-02T14:10:00+00:00")
        self.assertEqual(starts[3], "2026-09-13T05:33:27+00:00")
        self.assertEqual(starts[4], "2026-09-12T01:56:07+00:00")
        self.assertEqual(starts[5], "2026-09-11T04:13:20+00:00")

    def test_per_boot_record_shape(self):
        result = get_mini_ssd_boot_events(fake_runner)
        by_id = {boot["boot_id"]: boot for boot in result["boots"]}

        loss = by_id[LOSS_BOOT_ID]
        self.assertTrue(loss["available"])
        self.assertEqual(loss["index"], -2)
        self.assertEqual(loss["controller"], "nvme0")
        self.assertEqual(loss["suspend_count"], 1)
        self.assertEqual(len(loss["events"]), 4)
        self.assertEqual(loss["loss_episodes"], 1)
        self.assertTrue(loss["pcie_enumerated"])
        self.assertTrue(loss["nvme_probed"])

        quiet = by_id[QUIET_BOOT_ID]
        self.assertEqual(quiet["events"], [])
        self.assertEqual(quiet["suspend_count"], 2)
        self.assertEqual(quiet["loss_episodes"], 0)

        probe_fail = by_id[PROBE_FAIL_BOOT_ID]
        self.assertIsNone(probe_fail["controller"])
        self.assertTrue(probe_fail["pcie_enumerated"])
        self.assertFalse(probe_fail["nvme_probed"])
        self.assertEqual(probe_fail["loss_episodes"], 1)
        self.assertEqual(len(probe_fail["events"]), 2)
        self.assertEqual({event["kind"] for event in probe_fail["events"]}, {"loss"})

        absent = by_id[ABSENT_BOOT_ID]
        self.assertEqual(absent["events"], [])
        self.assertFalse(absent["pcie_enumerated"])
        self.assertFalse(absent["nvme_probed"])
        self.assertEqual(absent["loss_episodes"], 0)

        big = by_id[BIG_LOSS_BOOT_ID]
        self.assertEqual(big["loss_episodes"], 2)
        self.assertEqual(len(big["events"]), 28)

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
            "Mini SSD Events  : 4 loss episode(s) in 3 of 6 boot(s); 35 related line(s) "
            "(keyed by PCI 0000:c4:00.0, times UTC)",
        )
        self.assertIn(
            "   boot edb0b6bc (2026-09-12T01:56:07+00:00, nvme0, probed, suspends before first event: 0)",
            lines,
        )
        self.assertIn(
            "     2026-09-19T13:07:13+00:00 [loss] "
            "nvme nvme0: controller is down; will reset: CSTS=0xffffffff, PCI_STATUS=0x10",
            lines,
        )
        self.assertIn(
            "   boot aaaa1111 (2026-09-13T05:33:27+00:00, nvme1, probed, suspends before first event: 0)",
            lines,
        )
        self.assertIn(
            "   boot 1a2b3c4d (2026-10-01T15:00:01+00:00, no NVMe probe, PCIe only, no NVMe probe, "
            "suspends before first event: 0)",
            lines,
        )
        self.assertNotIn("   boot ffff5555", "\n".join(lines))

    def test_summary_never_cuts_loss_events(self):
        result = get_mini_ssd_boot_events(fake_runner)
        lines = format_summary({"mini_ssd_events": result}).splitlines()

        down_lines = [
            line
            for line in lines
            if line.startswith("     2026-08-29T16:48:22+00:00 [loss]") and "controller is down" in line
        ]
        self.assertEqual(len(down_lines), 1)
        self.assertTrue(
            any(
                line.startswith("     2026-08-29T18:58:09+00:00 [loss]") and "controller is down" in line
                for line in lines
            )
        )
        self.assertTrue(any(line.strip().startswith("… ") for line in lines))
        omitted = [line for line in lines if line.strip().startswith("… ")]
        self.assertRegex(omitted[0].strip(), r"^… \d+ more related line\(s\)$")

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
        self.assertFalse(by_id[LOSS_BOOT_ID]["pcie_enumerated"])
        self.assertFalse(by_id[LOSS_BOOT_ID]["nvme_probed"])
        self.assertEqual(by_id[LOSS_BOOT_ID]["loss_episodes"], 0)
        self.assertEqual(result["boots_with_events"], 3)
        self.assertEqual(result["boots_with_losses"], 2)
        self.assertEqual(result["loss_episodes"], 3)

    def test_invalid_json_is_unavailable(self):
        def bad_json_runner(argv: Sequence[str]) -> Tuple[int, str, str]:
            del argv
            return 0, "not json", ""

        result = get_mini_ssd_boot_events(bad_json_runner)
        self.assertFalse(result["available"])
        self.assertIn("invalid JSON", result["reason"])


if __name__ == "__main__":
    unittest.main()
