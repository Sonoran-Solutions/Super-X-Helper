"""Page components for the Super X Helper user interface."""

from superx_helper.ui.pages.base import BasePage
from superx_helper.ui.pages.cooling import CoolingPage
from superx_helper.ui.pages.dashboard import DashboardPage
from superx_helper.ui.pages.diagnostics import DiagnosticsPage
from superx_helper.ui.pages.display import DisplayPage
from superx_helper.ui.pages.performance import PerformancePage
from superx_helper.ui.pages.power import PowerPage
from superx_helper.ui.pages.profiles import ProfilesPage
from superx_helper.ui.pages.storage import StoragePage

__all__ = [
    "BasePage",
    "DashboardPage",
    "PerformancePage",
    "CoolingPage",
    "DisplayPage",
    "PowerPage",
    "StoragePage",
    "ProfilesPage",
    "DiagnosticsPage",
]
