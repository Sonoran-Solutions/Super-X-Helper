"""Frontend-facing service client abstraction.

The first UI can use LocalServiceClient during development. A D-Bus client will
implement the same small interface when the privileged service is wired.
"""

from __future__ import annotations

from typing import Any, Protocol

from superx_helper.contracts import CapabilitySnapshot, OperationResult
from superx_helper.service import SuperXService


class ServiceClient(Protocol):
    """Frontend-facing service surface.

    Both the in-process development client and the future D-Bus client
    implement this.  ``set_capability`` is typed and capability-scoped; it never
    exposes raw sysfs paths or shell strings.
    """

    def get_snapshot(self) -> CapabilitySnapshot:
        ...

    def set_capability(self, capability_id: str, value: Any) -> OperationResult:
        ...


class LocalServiceClient:
    def __init__(self, service: SuperXService):
        self.service = service

    def get_snapshot(self) -> CapabilitySnapshot:
        return self.service.get_capability_snapshot()

    def set_capability(self, capability_id: str, value: Any) -> OperationResult:
        return self.service.set_capability(capability_id, value)
