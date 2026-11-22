import os
import tempfile
import unittest
from unittest.mock import patch

from cfos_core import device_manager


class DeviceManagerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp.name, "devices.db")
        self.db_patch = patch.object(device_manager, "DB_PATH", self.db_path)
        self.db_patch.start()
        self.devices_patch = patch.object(device_manager, "usb_devices", return_value=[{
            "sysfs_name": "1-2", "vendor_id": "1234", "product_id": "5678",
            "manufacturer": "Test", "product": "USB Test Device"
        }])
        self.devices_patch.start()

    def tearDown(self):
        self.devices_patch.stop()
        self.db_patch.stop()
        self.tmp.cleanup()

    def test_reserve_and_list_marks_device_busy(self):
        result = device_manager.reserve("1-2", "windows-vm")
        self.assertEqual(result["owner"], "windows-vm")
        item = device_manager.list_devices()[0]
        self.assertFalse(item["available_to_cfos"])
        self.assertEqual(item["reservation"]["owner"], "windows-vm")

    def test_conflicting_reservation_is_rejected(self):
        device_manager.reserve("1-2", "windows-vm")
        with self.assertRaises(RuntimeError):
            device_manager.reserve("1-2", "android")

    def test_owner_must_match_when_releasing(self):
        device_manager.reserve("1-2", "windows-vm")
        with self.assertRaises(PermissionError):
            device_manager.release("1-2", "android")
        self.assertTrue(device_manager.release("1-2", "windows-vm")["released"])

    def test_cannot_reserve_missing_device(self):
        with self.assertRaises(ValueError):
            device_manager.reserve("9-9", "linux")

    def test_event_history(self):
        device_manager.record_event("add", {"sys_name": "1-2", "id_vendor": "1234"})
        events = device_manager.recent_events()
        self.assertEqual(events[0]["action"], "add")
        self.assertEqual(events[0]["device_id"], "1-2")


if __name__ == "__main__":
    unittest.main()
