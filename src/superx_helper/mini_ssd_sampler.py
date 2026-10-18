"""Periodic, read-only Mini SSD telemetry sampler.

Appends one JSON line per run to a capped log so the next controller loss comes
with pre-event link/ASPM/temperature context.  Sysfs reads only; the log file is
the only thing written.  Never a health verdict.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
from pathlib import Path
import sys
from typing import Dict, List, Optional

from superx_helper.storage import discover_mini_ssd, read_mini_ssd_telemetry

MAX_LINES = 50_000
# ponytail: size gate assumes every line is >100 bytes (lines are ~200+); skips
# re-reading the file each minute. Upgrade to a tracked line count if that changes.
_MIN_LINE_BYTES = 100


def default_log_path() -> Path:
    state = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
    return Path(state) / "superx-helper" / "mini-ssd-telemetry.jsonl"


def take_sample(sysfs_root: str = "", now: Optional[datetime.datetime] = None) -> Dict[str, object]:
    presence = discover_mini_ssd(sysfs_root)
    telemetry = read_mini_ssd_telemetry(presence.pci_address, sysfs_root)
    when = now or datetime.datetime.now(datetime.timezone.utc)
    return {
        "timestamp_utc": when.isoformat(timespec="seconds"),
        "state": presence.state.value,
        "pci_address": presence.pci_address,
        "controller": presence.controller,
        "link_speed": telemetry["link_speed"],
        "link_width": telemetry["link_width"],
        "max_link_speed": telemetry["max_link_speed"],
        "max_link_width": telemetry["max_link_width"],
        "aspm": telemetry["aspm"],
        "temperature_c": telemetry["temperature_c"],
    }


def append_sample(sample: Dict[str, object], log_path: Path, max_lines: int = MAX_LINES) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(sample, sort_keys=True) + "\n")
    if log_path.stat().st_size <= max_lines * _MIN_LINE_BYTES:
        return
    lines: List[str] = log_path.read_text(encoding="utf-8", errors="replace").splitlines(True)
    if len(lines) <= max_lines:
        return
    tmp = log_path.with_name(log_path.name + ".tmp")
    tmp.write_text("".join(lines[-max_lines:]), encoding="utf-8")
    os.replace(tmp, log_path)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Append one read-only Mini SSD telemetry sample.")
    parser.add_argument("-o", "--output", type=Path, default=None, help="log path (default: XDG state dir)")
    parser.add_argument("--sysfs-root", default="", help="alternate sysfs root (tests)")
    parser.add_argument("--max-lines", type=int, default=MAX_LINES)
    args = parser.parse_args(argv)
    try:
        append_sample(take_sample(args.sysfs_root), args.output or default_log_path(), args.max_lines)
    except OSError as exc:
        print(f"superx-mini-ssd-sample: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
