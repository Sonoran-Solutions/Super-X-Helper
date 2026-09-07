"""Transport-neutral service facade consumed by CLI, D-Bus and the future UI."""

from __future__ import annotations

import datetime as dt
from typing import Any, Dict, Iterable, Optional, Set

from superx_helper.capabilities import PlatformCapabilities
from superx_helper.collector import get_battery_info, get_display_info
from superx_helper.contracts import (
    CapabilityId,
    CapabilityRecord,
    CapabilitySnapshot,
    CapabilityStatus,
    OperationResult,
    SafetyState,
)
from superx_helper.platform import PlatformBackend


def coerce_capability_id(value: Any) -> Optional[CapabilityId]:
    """Resolve a transport-facing value to a stable capability id, if any."""
    if isinstance(value, CapabilityId):
        return value
    if isinstance(value, str):
        for member in CapabilityId:
            if member.value == value:
                return member
    return None


class SuperXService:
    """Stable application-facing facade.

    The future D-Bus service should serialize this contract instead of exposing
    raw sysfs paths or backend implementation details.  Mutations are typed and
    capability-scoped; authorization is decided here (service-side) and enforced
    again by the platform backend using the same stable capability ids.
    """

    def __init__(
        self,
        platform: Optional[PlatformBackend] = None,
        validated_writes: Optional[Iterable[str]] = None,
    ):
        self.validated_writes: Set[str] = set(validated_writes or [])
        self.platform = platform or PlatformBackend(
            authorized_writes=self.validated_writes
        )

    def _write_authorized(self, capability_id: CapabilityId) -> bool:
        return capability_id.value in self.validated_writes

    def set_capability(self, capability_id: Any, value: Any) -> OperationResult:
        """Apply a single capability-scoped mutation.

        The capability id is validated against the stable contract and must be
        production-authorized before the typed backend operation is dispatched.
        Read-only/unwritable capabilities fail closed here.
        """
        cid = coerce_capability_id(capability_id)
        if cid is None:
            return OperationResult(
                success=False,
                capability=str(capability_id),
                target_value=value,
                error_message=f"Unknown capability id {capability_id!r}.",
            )

        if not self._write_authorized(cid):
            return OperationResult(
                success=False,
                capability=cid.value,
                target_value=value,
                error_message=(
                    f"Write capability '{cid.value}' is not production-authorized "
                    "on this hardware."
                ),
            )

        if cid == CapabilityId.CPU_BOOST:
            if not isinstance(value, bool):
                return OperationResult(
                    success=False,
                    capability=cid.value,
                    target_value=value,
                    error_message="CPU Boost expects a boolean value.",
                )
            return self.platform.set_cpu_boost(value)

        if cid == CapabilityId.CPU_EPP:
            return self.platform.set_epp(str(value))

        if cid == CapabilityId.INTERNAL_FAN:
            try:
                duty = int(value)
            except (TypeError, ValueError):
                return OperationResult(
                    success=False,
                    capability=cid.value,
                    target_value=value,
                    error_message="Internal Fan expects an integer duty percentage.",
                )
            return self.platform.set_fan_duty(duty)

        if cid == CapabilityId.DISPLAY_BRIGHTNESS:
            try:
                percent = float(value)
            except (TypeError, ValueError):
                return OperationResult(
                    success=False,
                    capability=cid.value,
                    target_value=value,
                    error_message="Display Brightness expects a numeric percentage.",
                )
            return self.platform.set_display_brightness_percent(percent)

        return OperationResult(
            success=False,
            capability=cid.value,
            target_value=value,
            error_message=f"Capability '{cid.value}' is not a writable capability.",
        )

    def get_capability_snapshot(self) -> CapabilitySnapshot:
        """Return the cheap, UI-safe capability snapshot.

        Expensive diagnostics such as SMART and journal collection are kept out
        of normal UI refreshes and remain explicit diagnostic operations.
        """
        low = self.platform.refresh_capabilities()
        battery = get_battery_info()
        display = get_display_info()
        storage = {
            "mini_ssd": {
                "state": low.mini_ssd_classification,
                "pci_address": low.mini_ssd_pci_address,
                "controller": low.mini_ssd_controller,
                "namespaces": list(low.mini_ssd_namespaces),
                "reliability": "NOT_QUALIFIED",
            }
        }
        records = build_capability_records(
            low,
            self.platform,
            battery=battery,
            display=display,
            storage=storage,
            validated_writes=self.validated_writes,
        )
        return CapabilitySnapshot(
            schema_version=1,
            generated_at=dt.datetime.now(dt.timezone.utc).isoformat(),
            capabilities=records,
        )


def build_capability_records(
    low: PlatformCapabilities,
    platform: PlatformBackend,
    *,
    battery: Optional[Dict[str, object]] = None,
    display: Optional[Dict[str, object]] = None,
    storage: Optional[Dict[str, object]] = None,
    validated_writes: Optional[Iterable[str]] = None,
):
    validated = set(validated_writes or [])
    battery = battery or {}
    display = display or {}
    storage = storage or {}

    records = []

    def authorized(capability_id: CapabilityId) -> bool:
        return capability_id.value in validated

    if low.has_cpu_boost:
        records.append(
            CapabilityRecord(
                CapabilityId.CPU_BOOST.value,
                "CPU Boost",
                CapabilityStatus.CONFIRMED_LOCAL if authorized(CapabilityId.CPU_BOOST) else CapabilityStatus.SUPPORTED_UNVERIFIED,
                read_supported=True,
                write_supported=True,
                locally_validated=authorized(CapabilityId.CPU_BOOST),
                observed_value=platform.read_cpu_boost(),
                allowed_values=[False, True],
                owner="Linux cpufreq",
                backend="platform",
                write_authorized=authorized(CapabilityId.CPU_BOOST),
                reason_unavailable=None if authorized(CapabilityId.CPU_BOOST) else "Read path is confirmed; write behavior has not passed local production validation.",
                safety_state=SafetyState.NORMAL if authorized(CapabilityId.CPU_BOOST) else SafetyState.WARNING,
            )
        )
    else:
        records.append(_unavailable(CapabilityId.CPU_BOOST, "CPU Boost", "cpufreq boost interface not present."))

    if low.has_epp_control:
        records.append(
            CapabilityRecord(
                CapabilityId.CPU_EPP.value,
                "Energy Performance Preference",
                CapabilityStatus.CONFIRMED_LOCAL if authorized(CapabilityId.CPU_EPP) else CapabilityStatus.SUPPORTED_UNVERIFIED,
                read_supported=True,
                write_supported=True,
                locally_validated=authorized(CapabilityId.CPU_EPP),
                observed_value=platform.read_epp(),
                allowed_values=low.epp_available_preferences,
                owner="amd-pstate-epp",
                backend="platform",
                write_authorized=authorized(CapabilityId.CPU_EPP),
                reason_unavailable=None if authorized(CapabilityId.CPU_EPP) else "Read path is confirmed; write behavior has not passed local production validation.",
                safety_state=SafetyState.NORMAL if authorized(CapabilityId.CPU_EPP) else SafetyState.WARNING,
            )
        )
    else:
        records.append(_unavailable(CapabilityId.CPU_EPP, "Energy Performance Preference", "amd-pstate EPP interface not present."))

    records.append(
        CapabilityRecord(
            CapabilityId.POWER_TARGET.value,
            "Power Target",
            CapabilityStatus.SUPPORTED_UNVERIFIED if low.cpu_power_method != "none" else CapabilityStatus.UNAVAILABLE,
            read_supported=low.cpu_power_method != "none",
            write_supported=False,
            locally_validated=False,
            owner="Linux powercap / future validated adapter",
            backend="platform",
            reason_unavailable=(
                "Power telemetry/interface exists, but no production-qualified Super X power-target write path is selected yet."
                if low.cpu_power_method != "none"
                else "No supported power interface detected."
            ),
            safety_state=SafetyState.WARNING if low.cpu_power_method != "none" else SafetyState.UNKNOWN,
        )
    )

    fan_authorized = authorized(CapabilityId.INTERNAL_FAN)
    if low.has_fan_control:
        fan_status = CapabilityStatus.CONFIRMED_LOCAL if fan_authorized else CapabilityStatus.SUPPORTED_UNVERIFIED
        reason = None if fan_authorized else "oxpec hwmon path is present, but fan writes have not passed local production validation."
        records.append(
            CapabilityRecord(
                CapabilityId.INTERNAL_FAN.value,
                "Internal Fan",
                fan_status,
                read_supported=low.has_fan_telemetry,
                write_supported=True,
                locally_validated=fan_authorized,
                observed_value=platform.read_fan_duty(),
                minimum=0,
                maximum=100,
                unit="%",
                owner="oxpec / firmware EC",
                backend="platform",
                write_authorized=fan_authorized,
                reason_unavailable=reason,
                safety_state=SafetyState.NORMAL if fan_authorized else SafetyState.WARNING,
            )
        )
    elif low.oxpec_driver_available:
        records.append(
            CapabilityRecord(
                CapabilityId.INTERNAL_FAN.value,
                "Internal Fan",
                CapabilityStatus.SUPPORTED_UNVERIFIED,
                read_supported=False,
                write_supported=False,
                locally_validated=False,
                owner="oxpec / firmware EC",
                backend="platform",
                reason_unavailable="oxpec module is installed but not loaded; exact live hwmon attributes remain unverified.",
                safety_state=SafetyState.WARNING,
            )
        )
    else:
        records.append(_unavailable(CapabilityId.INTERNAL_FAN, "Internal Fan", "oxpec fan interface not detected."))

    if low.has_backlight_control:
        bright_authorized = authorized(CapabilityId.DISPLAY_BRIGHTNESS)
        records.append(
            CapabilityRecord(
                CapabilityId.DISPLAY_BRIGHTNESS.value,
                "Display Brightness",
                CapabilityStatus.CONFIRMED_LOCAL if bright_authorized else CapabilityStatus.SUPPORTED_UNVERIFIED,
                read_supported=True,
                write_supported=True,
                locally_validated=bright_authorized,
                observed_value=platform.read_display_brightness_percent(),
                minimum=0,
                maximum=100,
                unit="%",
                owner="amdgpu backlight",
                backend="platform",
                write_authorized=bright_authorized,
                reason_unavailable=None if bright_authorized else "Brightness telemetry is confirmed; direct write behavior has not passed production validation.",
                safety_state=SafetyState.NORMAL if bright_authorized else SafetyState.WARNING,
            )
        )
    else:
        records.append(_unavailable(CapabilityId.DISPLAY_BRIGHTNESS, "Display Brightness", "Backlight interface not detected."))

    connectors = display.get("connectors", []) if isinstance(display, dict) else []
    records.append(
        CapabilityRecord(
            CapabilityId.DISPLAY_MODE.value,
            "Display Mode",
            CapabilityStatus.READ_ONLY if connectors else CapabilityStatus.UNAVAILABLE,
            read_supported=bool(connectors),
            write_supported=False,
            locally_validated=bool(connectors),
            observed_value=connectors,
            owner="DRM/compositor",
            backend="telemetry",
            reason_unavailable=None if connectors else "No connected DRM display information available.",
            safety_state=SafetyState.NORMAL if connectors else SafetyState.UNKNOWN,
        )
    )

    battery_present = bool(battery.get("present")) if isinstance(battery, dict) else False
    records.append(
        CapabilityRecord(
            CapabilityId.BATTERY_TELEMETRY.value,
            "Battery",
            CapabilityStatus.READ_ONLY if battery_present else CapabilityStatus.UNAVAILABLE,
            read_supported=battery_present,
            write_supported=False,
            locally_validated=battery_present,
            observed_value=battery if battery_present else None,
            owner="power_supply",
            backend="telemetry",
            reason_unavailable=None if battery_present else "Battery telemetry not present.",
            safety_state=SafetyState.NORMAL if battery_present else SafetyState.UNKNOWN,
        )
    )
    records.append(
        CapabilityRecord(
            CapabilityId.BATTERY_CHARGE_CONTROL.value,
            "Charge Limit / Bypass",
            CapabilityStatus.UNAVAILABLE,
            read_supported=False,
            write_supported=False,
            locally_validated=False,
            owner="unknown",
            backend="platform",
            reason_unavailable="No trustworthy Linux charge-limit/bypass control path has been confirmed on this Super X.",
            safety_state=SafetyState.UNKNOWN,
        )
    )

    mini = storage.get("mini_ssd", {}) if isinstance(storage, dict) else {}
    mini_state = mini.get("state", low.mini_ssd_classification) if isinstance(mini, dict) else low.mini_ssd_classification
    mini_present = mini_state != "ABSENT"
    records.append(
        CapabilityRecord(
            CapabilityId.MINI_SSD_PRESENCE.value,
            "Mini SSD Presence",
            CapabilityStatus.READ_ONLY,
            read_supported=True,
            write_supported=False,
            locally_validated=True,
            observed_value=mini,
            owner="PCIe / Linux NVMe",
            backend="storage",
            reason_unavailable=None,
            warnings=[] if mini_present else ["Mini SSD is not currently visible at the PCIe endpoint."],
            safety_state=SafetyState.WARNING if not mini_present else SafetyState.NORMAL,
        )
    )
    records.append(
        CapabilityRecord(
            CapabilityId.MINI_SSD_RELIABILITY.value,
            "Mini SSD Reliability",
            CapabilityStatus.READ_ONLY,
            read_supported=True,
            write_supported=False,
            locally_validated=True,
            observed_value="NOT_QUALIFIED",
            owner="Super X Helper research",
            backend="storage",
            warnings=["Do not use the Mini SSD as the only copy of important data until reliability qualification passes."],
            safety_state=SafetyState.NOT_QUALIFIED,
        )
    )

    for capability_id, label in (
        (CapabilityId.FROST_BAY_TELEMETRY, "Frost Bay Telemetry"),
        (CapabilityId.FROST_BAY_CONTROL, "Frost Bay Control"),
    ):
        records.append(
            CapabilityRecord(
                capability_id.value,
                label,
                CapabilityStatus.RESEARCH_PENDING,
                read_supported=False,
                write_supported=False,
                locally_validated=False,
                owner="Super X Helper / BlueZ",
                backend="frost_bay",
                reason_unavailable="Frost Bay BLE protocol and health semantics have not been validated yet.",
                safety_state=SafetyState.BLOCKED,
            )
        )

    records.append(
        CapabilityRecord(
            CapabilityId.RGB_CONTROL.value,
            "RGB",
            CapabilityStatus.UNAVAILABLE,
            read_supported=False,
            write_supported=False,
            locally_validated=False,
            owner="unresolved",
            backend="device",
            reason_unavailable="No maintained or locally validated Linux RGB control path has been selected yet.",
            safety_state=SafetyState.UNKNOWN,
        )
    )
    records.append(
        CapabilityRecord(
            CapabilityId.CONTROLLER_INTEGRATION.value,
            "Controller / Gyro Integration",
            CapabilityStatus.SUPPORTED_UNVERIFIED,
            read_supported=False,
            write_supported=False,
            locally_validated=False,
            owner="HHD / InputPlumber / Steam",
            backend="external_integration",
            reason_unavailable="Super X Helper will integrate with the maintained input owner rather than implement another controller driver.",
            safety_state=SafetyState.NORMAL,
        )
    )
    records.append(
        CapabilityRecord(
            CapabilityId.DIAGNOSTICS_EXPORT.value,
            "Diagnostics Export",
            CapabilityStatus.CONFIRMED_LOCAL,
            read_supported=True,
            write_supported=False,
            locally_validated=True,
            owner="Super X Helper",
            backend="diagnostics",
            safety_state=SafetyState.NORMAL,
        )
    )
    return records


def _unavailable(capability_id: CapabilityId, label: str, reason: str) -> CapabilityRecord:
    return CapabilityRecord(
        capability_id.value,
        label,
        CapabilityStatus.UNAVAILABLE,
        read_supported=False,
        write_supported=False,
        locally_validated=False,
        reason_unavailable=reason,
        safety_state=SafetyState.UNKNOWN,
    )
