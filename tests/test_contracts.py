import unittest

from superx_helper.capabilities import PlatformCapabilities
from superx_helper.contracts import CapabilityId, CapabilityStatus, SafetyState
from superx_helper.service import build_capability_records


class FakePlatform:
    def read_cpu_boost(self): return True
    def read_epp(self): return "balance_performance"
    def read_fan_duty(self): return None
    def read_display_brightness_percent(self): return 80.0


class CapabilityContractTests(unittest.TestCase):
    def _records(self, validated=()):
        low = PlatformCapabilities(has_cpu_boost=True, has_epp_control=True, epp_available_preferences=["performance", "balance_performance"], cpu_power_method="rapl", has_backlight_control=True, oxpec_driver_available=True, has_mini_ssd=True, mini_ssd_classification="NVME_PRESENT")
        return build_capability_records(low, FakePlatform(), battery={"present": True, "capacity_pct": 90}, display={"connectors": [{"connector": "card1-eDP-1"}]}, storage={"mini_ssd": {"state": "NVME_PRESENT", "reliability": "NOT_QUALIFIED"}}, validated_writes=validated)

    def test_unverified_control_stays_disabled(self):
        records = {r.capability_id: r for r in self._records()}
        boost = records[CapabilityId.CPU_BOOST.value]
        self.assertEqual(boost.status, CapabilityStatus.SUPPORTED_UNVERIFIED)
        self.assertFalse(boost.locally_validated)
        self.assertFalse(boost.write_authorized)
        self.assertFalse(boost.can_write)

    def test_validated_control_can_be_enabled_by_contract(self):
        records = {r.capability_id: r for r in self._records(validated={CapabilityId.CPU_BOOST.value})}
        boost = records[CapabilityId.CPU_BOOST.value]
        self.assertEqual(boost.status, CapabilityStatus.CONFIRMED_LOCAL)
        self.assertTrue(boost.locally_validated)
        self.assertTrue(boost.write_authorized)
        self.assertTrue(boost.can_write)

    def test_frost_bay_is_research_pending(self):
        records = {r.capability_id: r for r in self._records()}
        for cap_id in (CapabilityId.FROST_BAY_TELEMETRY.value, CapabilityId.FROST_BAY_CONTROL.value):
            record = records[cap_id]
            self.assertEqual(record.status, CapabilityStatus.RESEARCH_PENDING)
            self.assertFalse(record.can_write)
            self.assertEqual(record.safety_state, SafetyState.BLOCKED)

    def test_mini_ssd_reliability_is_not_qualified(self):
        records = {r.capability_id: r for r in self._records()}
        reliability = records[CapabilityId.MINI_SSD_RELIABILITY.value]
        self.assertEqual(reliability.status, CapabilityStatus.READ_ONLY)
        self.assertEqual(reliability.observed_value, "NOT_QUALIFIED")
        self.assertEqual(reliability.safety_state, SafetyState.NOT_QUALIFIED)


if __name__ == "__main__":
    unittest.main()
