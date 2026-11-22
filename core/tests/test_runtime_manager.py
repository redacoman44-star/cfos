import unittest
from unittest.mock import patch, Mock
from cfos_core import runtime_manager


class RuntimeManagerTests(unittest.TestCase):
    def test_xml_uses_bus_device_address(self):
        xml = runtime_manager._xml({"bus_number": 2, "device_number": 7})
        self.assertIn("bus=\"2\"", xml)
        self.assertIn("device=\"7\"", xml)
        self.assertIn("managed=\"yes\"", xml)

    @patch.object(runtime_manager.os, "geteuid", return_value=1000)
    def test_requires_root(self, _mock):
        with self.assertRaises(PermissionError):
            runtime_manager._assert_root()

    @patch.object(runtime_manager, "usb_devices", create=True, return_value=[])
    def test_missing_device_rejected(self, _mock):
        with patch.object(runtime_manager, "_assert_root"):
            with self.assertRaises(ValueError):
                runtime_manager.passthrough("1-2", "win10")

    @patch.object(runtime_manager, "_interfaces", return_value=["03"])
    @patch.object(runtime_manager, "_find_device", return_value={"bus_number": 1, "device_number": 2})
    def test_hid_blocked(self, _find, _interfaces):
        with patch.object(runtime_manager, "_assert_root"), patch.object(runtime_manager, "_virsh") as virsh:
            with self.assertRaises(PermissionError):
                runtime_manager.passthrough("1-2", "win10")
            virsh.assert_not_called()

    @patch.object(runtime_manager, "_interfaces", return_value=["07"])
    @patch.object(runtime_manager, "_find_device", return_value={"bus_number": 1, "device_number": 2, "vendor_id": "1234", "product_id": "5678"})
    @patch.object(runtime_manager.device_manager, "reserve")
    @patch.object(runtime_manager.device_manager, "release")
    @patch.object(runtime_manager, "_virsh", return_value="running")
    @patch.object(runtime_manager.os, "geteuid", return_value=0)
    def test_printer_attach_uses_live_and_config_when_requested(self, *_mocks):
        with patch.object(runtime_manager, "_assert_root"), patch.object(runtime_manager, "_virsh", side_effect=["running", "", ""] ) as virsh:
            result = runtime_manager.passthrough("1-2", "win10", persistent=True)
        self.assertTrue(result["attached"])
        live, config = virsh.call_args_list[1].args[0], virsh.call_args_list[2].args[0]
        self.assertIn("--live", live)
        self.assertNotIn("--config", live)
        self.assertIn("--config", config)

    def test_vendor_specific_requires_explicit_opt_in(self):
        with patch.object(runtime_manager, "_assert_root"), \
             patch.object(runtime_manager, "_find_device", return_value={"bus_number": 1, "device_number": 2}), \
             patch.object(runtime_manager, "_interfaces", return_value=["ff"]), \
             patch.object(runtime_manager, "_virsh") as virsh:
            with self.assertRaises(PermissionError):
                runtime_manager.passthrough("1-2", "win10")
            virsh.assert_not_called()


if __name__ == "__main__":
    unittest.main()
