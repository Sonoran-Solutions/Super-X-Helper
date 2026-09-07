import unittest

from superx_helper.contracts import (
    CapabilityId,
    CapabilityRecord,
    CapabilitySnapshot,
    CapabilityStatus,
    OperationResult,
    SafetyState,
)
from superx_helper.service import SuperXService, coerce_capability_id
from superx_helper.transport import (
    operation_result_from_dict,
    snapshot_from_dict,
    snapshot_to_dict,
)


class FakePlatform:
    def __init__(self):
        self.calls = []

    def set_cpu_boost(self, value):
        self.calls.append((CapabilityId.CPU_BOOST.value, value))
        return OperationResult(True, CapabilityId.CPU_BOOST.value, value, observed_value=value)

    def set_epp(self, value):
        self.calls.append((CapabilityId.CPU_EPP.value, value))
        return OperationResult(True, CapabilityId.CPU_EPP.value, value, observed_value=value)

    def set_fan_duty(self, value):
        self.calls.append((CapabilityId.INTERNAL_FAN.value, value))
        return OperationResult(True, CapabilityId.INTERNAL_FAN.value, value, observed_value=value)

    def set_display_brightness_percent(self, value):
        self.calls.append((CapabilityId.DISPLAY_BRIGHTNESS.value, value))
        return OperationResult(True, CapabilityId.DISPLAY_BRIGHTNESS.value, value, observed_value=value)


class ServiceMutationTests(unittest.TestCase):
    def _service(self, validated=()):
        return SuperXService(platform=FakePlatform(), validated_writes=validated)

    def test_coerce_capability_id(self):
        self.assertEqual(coerce_capability_id("performance.cpu_boost"), CapabilityId.CPU_BOOST)
        self.assertEqual(coerce_capability_id(CapabilityId.CPU_EPP), CapabilityId.CPU_EPP)
        self.assertIsNone(coerce_capability_id("no.such.capability"))
        self.assertIsNone(coerce_capability_id(123))

    def test_unknown_capability_fails_closed(self):
        service = self._service()
        result = service.set_capability("no.such.capability", True)
        self.assertFalse(result.success)
        self.assertIn("Unknown capability", result.error_message)

    def test_unauthorized_capability_does_not_dispatch(self):
        service = self._service()
        result = service.set_capability(CapabilityId.CPU_BOOST.value, True)
        self.assertFalse(result.success)
        self.assertIn("not production-authorized", result.error_message)
        self.assertEqual(service.platform.calls, [])

    def test_authorized_dispatches_typed_operations(self):
        cases = [
            (CapabilityId.CPU_BOOST.value, True),
            (CapabilityId.CPU_EPP.value, "balance_power"),
            (CapabilityId.INTERNAL_FAN.value, 42),
            (CapabilityId.DISPLAY_BRIGHTNESS.value, 55.5),
        ]
        for capability_id, value in cases:
            with self.subTest(capability_id=capability_id):
                service = self._service(validated={capability_id})
                result = service.set_capability(capability_id, value)
                self.assertTrue(result.success)
                self.assertEqual(service.platform.calls, [(capability_id, value)])

    def test_boost_requires_boolean(self):
        service = self._service(validated={CapabilityId.CPU_BOOST.value})
        result = service.set_capability(CapabilityId.CPU_BOOST.value, "yes")
        self.assertFalse(result.success)
        self.assertIn("boolean", result.error_message)

    def test_fan_requires_integer(self):
        service = self._service(validated={CapabilityId.INTERNAL_FAN.value})
        result = service.set_capability(CapabilityId.INTERNAL_FAN.value, "fast")
        self.assertFalse(result.success)
        self.assertIn("integer", result.error_message)

    def test_brightness_requires_numeric(self):
        service = self._service(validated={CapabilityId.DISPLAY_BRIGHTNESS.value})
        result = service.set_capability(CapabilityId.DISPLAY_BRIGHTNESS.value, "dim")
        self.assertFalse(result.success)
        self.assertIn("numeric", result.error_message)


class TransportTests(unittest.TestCase):
    def _snapshot(self):
        record = CapabilityRecord(
            capability_id=CapabilityId.MINI_SSD_RELIABILITY.value,
            label="Mini SSD Reliability",
            status=CapabilityStatus.READ_ONLY,
            read_supported=True,
            write_supported=False,
            locally_validated=True,
            observed_value="NOT_QUALIFIED",
            owner="Super X Helper research",
            backend="storage",
            warnings=["Do not use the Mini SSD as the only copy of important data."],
            safety_state=SafetyState.NOT_QUALIFIED,
        )
        return CapabilitySnapshot(
            schema_version=1,
            generated_at="2026-09-07T00:00:00Z",
            capabilities=[record],
        )

    def test_snapshot_serialization_roundtrip(self):
        original = self._snapshot()
        data = snapshot_to_dict(original)
        rebuilt = snapshot_from_dict(data)

        self.assertEqual(rebuilt.schema_version, original.schema_version)
        self.assertEqual(rebuilt.generated_at, original.generated_at)
        self.assertEqual(len(rebuilt.capabilities), 1)

        rec = rebuilt.capabilities[0]
        self.assertEqual(rec.capability_id, CapabilityId.MINI_SSD_RELIABILITY.value)
        self.assertEqual(rec.status, CapabilityStatus.READ_ONLY)
        self.assertEqual(rec.safety_state, SafetyState.NOT_QUALIFIED)
        self.assertEqual(rec.observed_value, "NOT_QUALIFIED")
        self.assertEqual(rec.warnings, original.capabilities[0].warnings)
        # can_write is derived from serialized fields, never round-tripped.
        self.assertFalse(rec.can_write)

    def test_operation_result_serialization_roundtrip(self):
        original = OperationResult(
            success=False,
            capability=CapabilityId.INTERNAL_FAN.value,
            target_value=50,
            observed_value=None,
            error_message="Refusing fan-duty write: not authorized.",
            dry_run=False,
        )
        data = original.to_dict()
        rebuilt = operation_result_from_dict(data)
        self.assertFalse(rebuilt.success)
        self.assertEqual(rebuilt.capability, CapabilityId.INTERNAL_FAN.value)
        self.assertEqual(rebuilt.target_value, 50)
        self.assertIn("Refusing fan-duty write", rebuilt.error_message)


if __name__ == "__main__":
    unittest.main()
