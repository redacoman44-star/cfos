import unittest
from unittest.mock import patch
from cfos_core import hardware_profiles as hp

class HardwareProfileTests(unittest.TestCase):
    def test_classifies_usb_printer(self):
        with patch.object(hp, "_interface_classes", return_value=["07"]), patch.object(hp.Path, "resolve", side_effect=OSError):
            item=hp._usb_profile({"sysfs_name":"1-2","vendor_id":"03f0","product_id":"1234","product":"Printer"},{"usb_vendors":{"03f0":{"name":"HP"}},"usb_products":{}})
        self.assertEqual(item["function"],"printer")
        self.assertEqual(item["identification_confidence"],"vendor_match")

    def test_classifies_multifunction_device(self):
        with patch.object(hp, "_interface_classes", return_value=["06","07"]), patch.object(hp.Path, "resolve", side_effect=OSError):
            item=hp._usb_profile({"sysfs_name":"2-1","vendor_id":"04b8","product_id":"0001"},{"usb_vendors":{},"usb_products":{}})
        self.assertEqual(item["function"],"multifunction_print_scan")

    def test_vendor_match_is_not_exact_model(self):
        with patch.object(hp, "_interface_classes", return_value=[]), patch.object(hp.Path, "resolve", side_effect=OSError):
            item=hp._usb_profile({"sysfs_name":"3-1","vendor_id":"04a9","product_id":"9999"},{"usb_vendors":{"04a9":{"name":"Canon"}},"usb_products":{}})
        self.assertEqual(item["identification_confidence"],"vendor_match")
        self.assertIsNone(item["model_name"])

    def test_missing_device_profile_fails_cleanly(self):
        with patch.object(hp, "hardware_inventory", return_value={"usb":[]}):
            with self.assertRaises(ValueError): hp.profile_usb("missing")

if __name__ == "__main__": unittest.main()
