"""Transport-neutral serialization for the service boundary.

The future system D-Bus adapter will serialize the typed contract here and only
here.  These helpers are deliberately thin: they convert contract dataclasses
to/from plain dicts and delegate all semantics (``can_write``, status meanings,
authorization) to ``contracts``.  Nothing in this module imports a hardware
backend or re-derives capability behavior.
"""

from __future__ import annotations

from typing import Any, Dict, List

from superx_helper.contracts import (
    CapabilityRecord,
    CapabilitySnapshot,
    CapabilityStatus,
    OperationResult,
    SafetyState,
)

SERVICE_API_VERSION = 1


def snapshot_to_dict(snapshot: CapabilitySnapshot) -> Dict[str, Any]:
    return snapshot.to_dict()


def snapshot_from_dict(data: Dict[str, Any]) -> CapabilitySnapshot:
    records: List[CapabilityRecord] = [
        record_from_dict(item) for item in data.get("capabilities", [])
    ]
    return CapabilitySnapshot(
        schema_version=int(data.get("schema_version", 1)),
        generated_at=str(data.get("generated_at", "")),
        capabilities=records,
    )


def record_from_dict(data: Dict[str, Any]) -> CapabilityRecord:
    """Rebuild a capability record; ``can_write`` is derived, never serialized."""
    return CapabilityRecord(
        capability_id=str(data["capability_id"]),
        label=str(data.get("label", data["capability_id"])),
        status=CapabilityStatus(data["status"]),
        read_supported=bool(data.get("read_supported", False)),
        write_supported=bool(data.get("write_supported", False)),
        locally_validated=bool(data.get("locally_validated", False)),
        observed_value=data.get("observed_value"),
        desired_value=data.get("desired_value"),
        allowed_values=list(data.get("allowed_values", [])),
        minimum=data.get("minimum"),
        maximum=data.get("maximum"),
        unit=data.get("unit"),
        owner=str(data.get("owner", "unknown")),
        backend=str(data.get("backend", "unknown")),
        write_authorized=bool(data.get("write_authorized", False)),
        reason_unavailable=data.get("reason_unavailable"),
        warnings=list(data.get("warnings", [])),
        safety_state=SafetyState(data.get("safety_state", SafetyState.UNKNOWN.value)),
    )


def operation_result_to_dict(result: OperationResult) -> Dict[str, Any]:
    return result.to_dict()


def operation_result_from_dict(data: Dict[str, Any]) -> OperationResult:
    return OperationResult.from_dict(data)
