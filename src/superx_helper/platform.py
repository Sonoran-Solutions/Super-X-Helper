"""Validated platform operations for Super X Helper.

Interface discovery and write authorization are deliberately separate.  The
backend defaults to no authorized writes until a hardware path has passed the
research-to-production gate.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Set

from superx_helper.capabilities import PlatformCapabilities, detect_capabilities

logger = logging.getLogger(__name__)


@dataclass
class OperationResult:
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
    def __init__(
        self,
        sysfs_root: str = "",
        dry_run: bool = False,
        authorized_writes: Optional[Iterable[str]] = None,
    ):
        self.sysfs_root = sysfs_root
        self.dry_run = dry_run
        self.authorized_writes: Set[str] = set(authorized_writes or [])
        self.capabilities = detect_capabilities(sysfs_root=sysfs_root)

    def refresh_capabilities(self) -> PlatformCapabilities:
        self.capabilities = detect_capabilities(sysfs_root=self.sysfs_root)
        return self.capabilities

    def is_write_authorized(self, capability: str) -> bool:
        return capability in self.authorized_writes

    def _blocked(self, capability: str, target_value: Any) -> OperationResult:
        return OperationResult(
            success=False,
            capability=capability,
            target_value=target_value,
            error_message=(
                f"Write capability '{capability}' is not production-authorized on this hardware."
            ),
        )

    def _safe_write(
        self,
        path_str: Optional[str],
        value: str,
        capability: str,
    ) -> OperationResult:
        if not self.is_write_authorized(capability):
            return self._blocked(capability, value)
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
            if observed != value:
                return OperationResult(
                    success=False,
                    capability=capability,
                    target_value=value,
                    observed_value=observed,
                    error_message=(
                        f"Write did not verify: requested {value!r}, observed {observed!r}."
                    ),
                )
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
                    f"Permission denied writing to {target_path}. Privileged service authorization required."
                ),
            )
        except OSError as exc:
            return OperationResult(
                success=False,
                capability=capability,
                target_value=value,
                error_message=f"Write failed: {exc}",
            )

    def read_fan_duty(self) -> Optional[int]:
        if not self.capabilities.has_fan_telemetry or not self.capabilities.fan_pwm_path:
            return None
        try:
            raw_pwm = int(Path(self.capabilities.fan_pwm_path).read_text().strip())
            return round((raw_pwm / 255.0) * 100)
        except (OSError, ValueError):
            return None

    def set_fan_duty(self, duty_percent: int) -> OperationResult:
        if not (0 <= duty_percent <= 100):
            return OperationResult(
                success=False,
                capability="fan_control",
                target_value=duty_percent,
                error_message=f"Duty cycle {duty_percent}% is out of valid range [0, 100].",
            )
        if not self.is_write_authorized("fan_control"):
            return self._blocked("fan_control", duty_percent)
        if not self.capabilities.has_fan_control or not self.capabilities.fan_pwm_path:
            return OperationResult(
                success=False,
                capability="fan_control",
                target_value=duty_percent,
                error_message="Internal fan control interface is not available.",
            )

        if self.capabilities.fan_pwm_enable_path:
            previous = set(self.authorized_writes)
            self.authorized_writes.add("fan_manual_enable")
            try:
                mode_result = self._safe_write(
                    self.capabilities.fan_pwm_enable_path,
                    "1",
                    "fan_manual_enable",
                )
            finally:
                self.authorized_writes = previous
            if not mode_result.success:
                return OperationResult(
                    success=False,
                    capability="fan_control",
                    target_value=duty_percent,
                    observed_value=mode_result.observed_value,
                    error_message=(
                        "Refusing fan-duty write because manual fan mode could not be verified: "
                        f"{mode_result.error_message}"
                    ),
                )

        raw_pwm = int(round((duty_percent / 100.0) * 255))
        result = self._safe_write(self.capabilities.fan_pwm_path, str(raw_pwm), "fan_control")
        if result.observed_value is not None:
            try:
                observed_raw = int(result.observed_value)
                result.observed_value = round((observed_raw / 255.0) * 100)
            except (TypeError, ValueError):
                pass
        result.target_value = duty_percent
        return result

    def set_fan_auto(self) -> OperationResult:
        if not self.capabilities.has_fan_control or not self.capabilities.fan_pwm_enable_path:
            return OperationResult(
                success=False,
                capability="fan_auto",
                target_value=True,
                error_message="Internal fan mode control is not available.",
            )
        return self._safe_write(self.capabilities.fan_pwm_enable_path, "2", "fan_auto")

    def read_epp(self) -> Optional[str]:
        if not self.capabilities.has_epp_control or not self.capabilities.epp_path:
            return None
        try:
            return Path(self.capabilities.epp_path).read_text().strip()
        except OSError:
            return None

    def set_epp(self, preference: str) -> OperationResult:
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

    def read_cpu_boost(self) -> Optional[bool]:
        if not self.capabilities.has_cpu_boost or not self.capabilities.cpu_boost_path:
            return None
        try:
            return Path(self.capabilities.cpu_boost_path).read_text().strip() == "1"
        except OSError:
            return None

    def set_cpu_boost(self, enable: bool) -> OperationResult:
        if not self.capabilities.has_cpu_boost or not self.capabilities.cpu_boost_path:
            return OperationResult(
                success=False,
                capability="cpu_boost",
                target_value=enable,
                error_message="CPU boost control path not found.",
            )
        result = self._safe_write(
            self.capabilities.cpu_boost_path,
            "1" if enable else "0",
            "cpu_boost",
        )
        result.target_value = enable
        if result.observed_value in {"0", "1"}:
            result.observed_value = result.observed_value == "1"
        return result

    def read_display_brightness_percent(self) -> Optional[float]:
        if (
            not self.capabilities.has_backlight_control
            or not self.capabilities.backlight_path
            or not self.capabilities.backlight_max
        ):
            return None
        try:
            actual = int(Path(self.capabilities.backlight_path).read_text().strip())
            return round((actual / self.capabilities.backlight_max) * 100.0, 1)
        except (OSError, ValueError):
            return None

    def set_display_brightness_percent(self, percent: float) -> OperationResult:
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

        raw_value = int(round((percent / 100.0) * self.capabilities.backlight_max))
        result = self._safe_write(self.capabilities.backlight_path, str(raw_value), "backlight")
        result.target_value = percent
        if result.observed_value is not None:
            try:
                result.observed_value = round(
                    (int(result.observed_value) / self.capabilities.backlight_max) * 100.0,
                    1,
                )
            except (TypeError, ValueError):
                pass
        return result
