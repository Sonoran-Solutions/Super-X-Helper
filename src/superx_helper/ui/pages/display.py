"""Display configuration page."""

from __future__ import annotations

from typing import Optional

from superx_helper.contracts import CapabilityId
from superx_helper.ui.pages.base import BasePage
from superx_helper.ui_manifest import PageSpec


class DisplayPage(BasePage):
    """Display and backlight controls page."""

    def __init__(self, spec: Optional[PageSpec] = None):
        super().__init__(
            spec
            or PageSpec(
                "display",
                "Display",
                [
                    CapabilityId.DISPLAY_BRIGHTNESS.value,
                    CapabilityId.DISPLAY_MODE.value,
                ],
            )
        )
