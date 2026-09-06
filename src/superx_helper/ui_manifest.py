"""Page manifest for the pre-Astra UI.

Tier-1 frontend work can build these pages mechanically against the stable
capability IDs without importing hardware backends.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from superx_helper.contracts import CapabilityId


@dataclass(frozen=True)
class PageSpec:
    page_id: str
    title: str
    capability_ids: List[str]


PAGES = [
    PageSpec("dashboard", "Dashboard", [CapabilityId.CPU_BOOST.value, CapabilityId.CPU_EPP.value, CapabilityId.INTERNAL_FAN.value, CapabilityId.BATTERY_TELEMETRY.value, CapabilityId.DISPLAY_MODE.value, CapabilityId.MINI_SSD_PRESENCE.value, CapabilityId.MINI_SSD_RELIABILITY.value, CapabilityId.FROST_BAY_TELEMETRY.value]),
    PageSpec("performance", "Performance", [CapabilityId.CPU_BOOST.value, CapabilityId.CPU_EPP.value, CapabilityId.POWER_TARGET.value]),
    PageSpec("cooling", "Cooling", [CapabilityId.INTERNAL_FAN.value, CapabilityId.FROST_BAY_TELEMETRY.value, CapabilityId.FROST_BAY_CONTROL.value]),
    PageSpec("display", "Display", [CapabilityId.DISPLAY_BRIGHTNESS.value, CapabilityId.DISPLAY_MODE.value]),
    PageSpec("power", "Power / Battery", [CapabilityId.BATTERY_TELEMETRY.value, CapabilityId.BATTERY_CHARGE_CONTROL.value, CapabilityId.CPU_BOOST.value, CapabilityId.CPU_EPP.value]),
    PageSpec("storage", "Storage", [CapabilityId.MINI_SSD_PRESENCE.value, CapabilityId.MINI_SSD_RELIABILITY.value]),
    PageSpec("profiles", "Profiles", []),
    PageSpec("diagnostics", "Diagnostics", [CapabilityId.DIAGNOSTICS_EXPORT.value]),
]
