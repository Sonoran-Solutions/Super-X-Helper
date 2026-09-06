"""Platform backend implementing safe, validated control operations for Super X Helper.

Follows the design principles in DESIGN.md and AGENTS.md:
- Never accept arbitrary sysfs paths from callers.
- Enforce strict range checks before any write operation.
- Verify observed state against desired state.
- Gracefully handle permission limitations.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from superx_helper.capabilities import PlatformCapabilities, detect_capabilities

logger = logging.getLogger(__name__)


@dataclass
class OperationResult:
    """Outcome of a platform control operation."""

    success: bool
    capability: str
    target_value: Any
    observed_value: Any = None
    error_message: Optional[str] = None
    dry_run: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "capability": self.capability,
            "target_value": self.target_value,
            "observed_value": self.observed_value,
            "error_message": self.error_message,
            "dry_run": self.dry_run,
        }


class PlatformBackend:
    """Safe, typed interface for Super X platform hardware controls."""

    def __init__(self, sysfs_root: str = "", dry_run: bool = False):
        self.sysfs_root = sysfs_root
        self.dry_run = dry_run
        self.capabilities = detect_capabilities(sysfs_root=sysfs_root)

    def refresh_capabilities(self) -> PlatformCapabilities:
        """Re-scan platform capabilities and return updated state."""
        self.capabilities = detect_capabilities(sysfs_root=self.sysfs_root)
        return self.capabilities

    def _safe_write(self, path_str: Optional[str], value: str, capability: str) -> OperationResult:
        """Write safely to a validated sysfs path with error interception."""
        if not path_str:
            return OperationResult(
                success=False,
                capability=capability,
                target_value=value,
                error_message=f"No sysfs path resolved for capability '{capability}'.",
            )

        target_path = Path(path_str)
        if self.dry_run:
            logger.info("[DRY RUN] Would write '%s' to %s", value, target_path)
            return OperationResult(
                success=True,
                capability=capability,
                target_value=value,
                observed_value=value,
                dry_run=True,
            )

        try:
            target_path.write_text(value + "\n", encoding="utf-8")
            observed = target_path.read_text(encoding="utf-8").strip()
            return OperationResult(
                success=True,
                capability=capability,
                target_value=value,
                observed_value=observed,
            )
        except PermissionError:
            return OperationResult(
                success=False,
                capability=capability,
                target_value=value,
                error_message=(
                    f"Permission denied writing to {target_path}. Elevated daemon privileges required."
                ),
            )
        except Exception as exc:
            return OperationResult(
                success=False,
                capability=capability,
                target_value=value,
                error_message=f"Write failed: {exc}",
            )

    # -------------------------------------------------------------------------
    # Fan Controls (oxpec hwmon)
    # -------------------------------------------------------------------------

    def read_fan_duty(self) -> Optional[int]:
        """Read current internal fan duty cycle as a percentage (0..100%)."""
        if not self.capabilities.has_fan_telemetry or not self.capabilities.fan_pwm_path:
            return None
        try:
            raw_pwm = int(Path(self.capabilities.fan_pwm_path).read_text(encoding="utf-8").strip())
            return round((raw_pwm / 255.0) * 100)
        except Exception:
            return None

    def set_fan_duty(self, duty_percent: int) -> OperationResult:
        """Set internal fan duty percentage (0..100%).

        Validates duty cycle, converts to 0..255 PWM scale, and writes to oxpec hwmon.
        """
        if not (0 <= duty_percent <= 100):
            return OperationResult(
                success=False,
                capability="fan_control",
                target_value=duty_percent,
                error_message=f"Duty cycle {duty_percent}% is out of valid range [0, 100].",
            )

        if not self.capabilities.has_fan_control or not self.capabilities.fan_pwm_path:
            return OperationResult(
                success=False,
                capability="fan_control",
                target_value=duty_percent,
                error_message="Internal fan control is not available (oxpec driver not loaded).",
            )

        # Ensure manual control mode is active if pwm1_enable exists (usually mode 1)
        if self.capabilities.fan_pwm_enable_path:
            self._safe_write(self.capabilities.fan_pwm_enable_path, "1", "fan_manual_enable")

        raw_pwm = int(round((duty_percent / 100.0) * 255))
        res = self._safe_write(self.capabilities.fan_pwm_path, str(raw_pwm), "fan_duty")
        if res.success and res.observed_value is not None:
            try:
                observed_int = int(res.observed_value)
                res.observed_value = round((observed_int / 255.0) * 100)
            except ValueError:
                pass
        return res

    def set_fan_auto(self) -> OperationResult:
        """Restore automatic EC-controlled fan curve (pwm1_enable = 2)."""
        if not self.capabilities.has_fan_control or not self.capabilities.fan_pwm_enable_path:
            return OperationResult(
                success=False,
                capability="fan_auto",
                target_value=True,
                error_message="Internal fan mode control is not available.",
            )
        return self._safe_write(self.capabilities.fan_pwm_enable_path, "2", "fan_auto")

    # -------------------------------------------------------------------------
    # CPU Scaling & Boost
    # -------------------------------------------------------------------------

    def read_epp(self) -> Optional[str]:
        """Read active Energy Performance Preference."""
        if not self.capabilities.has_epp_control or not self.capabilities.epp_path:
            return None
        try:
            return Path(self.capabilities.epp_path).read_text(encoding="utf-8").strip()
        except Exception:
            return None

    def set_epp(self, preference: str) -> OperationResult:
        """Set Energy Performance Preference with validation against available profiles."""
        pref_clean = preference.strip().lower()
        if (
            self.capabilities.epp_available_preferences
            and pref_clean not in self.capabilities.epp_available_preferences
        ):
            return OperationResult(
                success=False,
                capability="epp",
                target_value=preference,
                error_message=(
                    f"Preference '{preference}' invalid. Allowed: {self.capabilities.epp_available_preferences}"
                ),
            )

        return self._safe_write(self.capabilities.epp_path, pref_clean, "epp")

    def set_cpu_boost(self, enable: bool) -> OperationResult:
        """Enable or disable CPU boost flag (0 or 1)."""
        if not self.capabilities.has_cpu_boost or not self.capabilities.cpu_boost_path:
            return OperationResult(
                success=False,
                capability="cpu_boost",
                target_value=enable,
                error_message="CPU boost control path not found.",
            )
        val = "1" if enable else "0"
        return self._safe_write(self.capabilities.cpu_boost_path, val, "cpu_boost")

    # -------------------------------------------------------------------------
    # Display Brightness
    # -------------------------------------------------------------------------

    def read_display_brightness_percent(self) -> Optional[float]:
        """Read current display brightness as a percentage."""
        if (
            not self.capabilities.has_backlight_control
            or not self.capabilities.backlight_path
            or not self.capabilities.backlight_max
        ):
            return None
        try:
            actual = int(Path(self.capabilities.backlight_path).read_text(encoding="utf-8").strip())
            return round((actual / self.capabilities.backlight_max) * 100.0, 1)
        except Exception:
            return None

    def set_display_brightness_percent(self, percent: float) -> OperationResult:
        """Set display brightness percentage (0.0 .. 100.0%)."""
        if not (0.0 <= percent <= 100.0):
            return OperationResult(
                success=False,
                capability="backlight",
                target_value=percent,
                error_message=f"Brightness {percent}% is out of valid range [0.0, 100.0].",
            )
        if (
            not self.capabilities.has_backlight_control
            or not self.capabilities.backlight_path
            or not self.capabilities.backlight_max
        ):
            return OperationResult(
                success=False,
                capability="backlight",
                target_value=percent,
                error_message="Backlight control path or max brightness not resolved.",
            )

        raw_val = int(round((percent / 100.0) * self.capabilities.backlight_max))
        res = self._safe_write(self.capabilities.backlight_path, str(raw_val), "backlight")
        if res.success and res.observed_value is not None:
            try:
                obs_raw = int(res.observed_value)
                res.observed_value = round((obs_raw / self.capabilities.backlight_max) * 100.0, 1)
            except ValueError:
                pass
        return res
