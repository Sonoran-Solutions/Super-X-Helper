"""Frontend-facing service client abstraction.

The first UI can use LocalServiceClient during development. A D-Bus client will
implement the same small interface when the privileged service is wired.
"""

from __future__ import annotations

from typing import Protocol

from superx_helper.contracts import CapabilitySnapshot
from superx_helper.service import SuperXService


class ServiceClient(Protocol):
    def get_snapshot(self) -> CapabilitySnapshot:
        ...


class LocalServiceClient:
    def __init__(self, service: SuperXService):
        self.service = service

    def get_snapshot(self) -> CapabilitySnapshot:
        return self.service.get_capability_snapshot()
