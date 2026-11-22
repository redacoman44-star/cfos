import unittest
from unittest.mock import patch
from cfos_core import collector

class CollectorTests(unittest.TestCase):
    def test_status_has_required_fields(self):
        result = collector.status()
        for key in ("name", "version", "host_os", "architecture"):
            self.assertIn(key, result)

    def test_resources_are_non_negative(self):
        result = collector.resources()
        self.assertGreaterEqual(result["cpu_count"], 0)
        for key in ("memory_total_bytes", "memory_available_bytes", "memory_used_bytes"):
            self.assertGreaterEqual(result[key], 0)

    def test_dispatch_rejects_unknown_command(self):
        with self.assertRaises(ValueError):
            collector.collect("shutdown")

    @patch("cfos_core.device_manager.usb_devices", return_value=[])
    def test_devices_shape(self, _mock):
        self.assertEqual(collector.collect("devices"), {"usb": []})

if __name__ == "__main__":
    unittest.main()
