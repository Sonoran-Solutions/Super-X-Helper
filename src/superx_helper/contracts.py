"""Stable backend/UI contracts for Super X Helper.

The UI consumes these transport-neutral records.  Hardware discovery and write
authorization remain separate concerns so merely detecting a writable sysfs node
never enables a control in the UI.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class CapabilityStatus(str, Enum):
    CONFIRMED_LOCAL = "CONFIRMED_LOCAL"
    SUPPORTED_UNVERIFIED = "SUPPORTED_UNVERIFIED"
    READ_ONLY = "READ_ONLY"
    RESEARCH_PENDING = "RESEARCH_PENDING"
    UNAVAILABLE = "UNAVAILABLE"
    ERROR = "ERROR"


class SafetyState(str, Enum):
    NORMAL = "NORMAL"
    WARNING = "WARNING"
    NOT_QUALIFIED = "NOT_QUALIFIED"
    BLOCKED = "BLOCKED"
    UNKNOWN = "UNKNOWN"
    ERROR = "ERROR"


class CapabilityId(str, Enum):
    CPU_BOOST = "performance.cpu_boost"
    CPU_EPP = "performance.epp"
    POWER_TARGET = "performance.power_target"
    INTERNAL_FAN = "cooling.internal_fan"
    FROST_BAY_TELEMETRY = "cooling.frost_bay.telemetry"
    FROST_BAY_CONTROL = "cooling.frost_bay.control"
    DISPLAY_BRIGHTNESS = "display.brightness"
    DISPLAY_MODE = "display.mode"
    BATTERY_TELEMETRY = "power.battery"
    BATTERY_CHARGE_CONTROL = "power.charge_control"
    MINI_SSD_PRESENCE = "storage.mini_ssd.presence"
    MINI_SSD_RELIABILITY = "storage.mini_ssd.reliability"
    RGB_CONTROL = "device.rgb"
    CONTROLLER_INTEGRATION = "device.controller_integration"
    DIAGNOSTICS_EXPORT = "diagnostics.export"


@dataclass(frozen=True)
class CapabilityRecord:
    """One normalized capability exposed to the UI.

    ``write_supported`` describes the discovered interface semantics.
    ``write_authorized`` describes current policy.  The UI may only enable a
    control when both are true and the capability has passed local validation.
    """

    capability_id: str
    label: str
    status: CapabilityStatus
    read_supported: bool
    write_supported: bool
    locally_validated: bool
    observed_value: Any = None
    desired_value: Any = None
    allowed_values: List[Any] = field(default_factory=list)
    minimum: Optional[float] = None
    maximum: Optional[float] = None
    unit: Optional[str] = None
    owner: str = "unknown"
    backend: str = "unknown"
    write_authorized: bool = False
    reason_unavailable: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    safety_state: SafetyState = SafetyState.UNKNOWN

    @property
    def can_write(self) -> bool:
        return (
            self.write_supported
            and self.write_authorized
            and self.locally_validated
            and self.status == CapabilityStatus.CONFIRMED_LOCAL
        )

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        data["safety_state"] = self.safety_state.value
        data["can_write"] = self.can_write
        return data


@dataclass(frozen=True)
class CapabilitySnapshot:
    schema_version: int
    generated_at: str
    capabilities: List[CapabilityRecord]

    def by_id(self, capability_id: str) -> Optional[CapabilityRecord]:
        return next(
            (item for item in self.capabilities if item.capability_id == capability_id),
            None,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "generated_at": self.generated_at,
            "capabilities": [item.to_dict() for item in self.capabilities],
        }
