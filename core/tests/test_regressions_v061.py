import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cfos_core import collector, hardware_profiles as hp


class BoundDriverTests(unittest.TestCase):
    def test_missing_driver_symlink_means_no_driver(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(collector.bound_driver(tmp))

    def test_symlink_returns_driver_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "drivers" / "e1000e"
            target.mkdir(parents=True)
            dev = Path(tmp) / "dev"
            dev.mkdir()
            os.symlink(target, dev / "driver")
            self.assertEqual(collector.bound_driver(dev), "e1000e")

    def test_nonexistent_device_path_is_safe(self):
        self.assertIsNone(collector.bound_driver("/nonexistent/cfos/device"))


class InventorySummaryTests(unittest.TestCase):
    def test_summary_with_non_network_pci_does_not_raise(self):
        pci = [{"device_id": "0000:00:00.0", "category": "other", "needs_driver_review": False},
               {"device_id": "0000:00:1f.6", "category": "network", "needs_driver_review": True}]
        usb = [{"device_id": "1-2", "function": "printer", "needs_driver_review": True},
               {"device_id": "1-3", "function": "network_adapter", "needs_driver_review": False}]
        with patch.object(hp, "pci_devices", return_value=pci), \
             patch.object(hp, "usb_devices", return_value=[{"sysfs_name": "1-2"}, {"sysfs_name": "1-3"}]), \
             patch.object(hp, "_usb_profile", side_effect=usb):
            summary = hp.hardware_inventory()["summary"]
        self.assertEqual(summary["pci_count"], 2)
        self.assertEqual(summary["usb_count"], 2)
        self.assertEqual(summary["printers_or_multifunction"], 1)
        self.assertEqual(summary["network_adapters"], 2)
        self.assertEqual(summary["driver_review_candidates"], 2)


if __name__ == "__main__":
    unittest.main()
