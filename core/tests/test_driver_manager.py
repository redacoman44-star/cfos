import unittest
from unittest.mock import patch
from cfos_core import driver_manager as dm

class DriverManagerTests(unittest.TestCase):
    def test_alias_resolution_sanitizes_module_names(self):
        with patch.object(dm.shutil, "which", return_value="/sbin/modprobe"), \
             patch.object(dm, "_run", return_value="usbhid\nfoo-bar\ninvalid name\n"):
            self.assertEqual(dm._module_candidates("usb:v1234p5678"), ["foo-bar", "usbhid"])

    def test_no_modprobe_returns_no_candidates(self):
        with patch.object(dm.shutil, "which", return_value=None):
            self.assertEqual(dm._module_candidates("alias"), [])

    def test_bound_driver_state_does_not_suggest_install(self):
        with patch.object(dm, "_module_candidates", return_value=[]):
            item = dm._inspect("PCI", "0000:00:01.0", "pci:v00008086", "i915")
        self.assertEqual(item["driver_state"], "driver_bound")
        self.assertFalse(item["installation_performed"])
        self.assertEqual(item["candidate_modules"], [])

    def test_alias_without_bound_driver_is_candidate_not_install(self):
        with patch.object(dm, "_module_candidates", return_value=["e1000e"]), \
             patch.object(dm, "_module_details", return_value={"module":"e1000e","loaded":False}):
            item = dm._inspect("PCI", "0000:00:1f.6", "pci:alias", None)
        self.assertEqual(item["driver_state"], "matching_module_available")
        self.assertFalse(item["installation_performed"])

    def test_empty_device_rejected(self):
        with self.assertRaises(ValueError):
            dm.inspect_device(" ")

if __name__ == "__main__":
    unittest.main()
