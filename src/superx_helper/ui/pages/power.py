"""Power and battery management page."""

from __future__ import annotations

from typing import Optional

from superx_helper.contracts import CapabilityId
from superx_helper.ui.pages.base import BasePage
from superx_helper.ui_manifest import PageSpec


class PowerPage(BasePage):
    """Power and battery management page."""

    def __init__(self, spec: Optional[PageSpec] = None):
        super().__init__(
            spec
            or PageSpec(
                "power",
                "Power / Battery",
                [
                    CapabilityId.BATTERY_TELEMETRY.value,
                    CapabilityId.BATTERY_CHARGE_CONTROL.value,
                    CapabilityId.CPU_BOOST.value,
                    CapabilityId.CPU_EPP.value,
                ],
            )
        )
