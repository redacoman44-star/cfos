import os, tempfile, unittest
from unittest.mock import patch
from cfos_core import device_manager, lifecycle, runtime_manager as rm, install_manager as im
from pathlib import Path

DEV = {"sysfs_name": "1-2", "vendor_id": "04a9", "product_id": "2709", "bus_number": "1", "device_number": "5"}

def dom_xml(addr=None, ids=None):
    src = f"<address bus='{addr[0]}' device='{addr[1]}'/>" if addr else f"<vendor id='{ids[0]}'/><product id='{ids[1]}'/>"
    return f"<domain><devices><hostdev mode='subsystem' type='usb' managed='yes'><source>{src}</source></hostdev></devices></domain>"

class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ps = [patch.object(device_manager, "DB_PATH", os.path.join(self.tmp.name, "d.db")),
                   patch.object(im, "AUDIT_LOG", Path(self.tmp.name) / "audit.log"),
                   patch.object(device_manager, "usb_devices", return_value=[DEV])]
        for x in self.ps: x.start()
    def tearDown(self):
        for x in self.ps: x.stop()
        self.tmp.cleanup()

    def run_reconcile(self, present, domains=None, live=None, inactive=None):
        domains = domains or {}
        def virsh(args):
            if args[0] == "list": return "\n".join(domains)
            if args[0] == "domstate": return domains[args[1]]
            if args[0] == "dumpxml":
                if args[1] == "--inactive": return (inactive or {}).get(args[2], dom_xml(ids=("0x0", "0x0")))
                return (live or {}).get(args[1], dom_xml(ids=("0x0", "0x0")))
            raise AssertionError(args)
        with patch.object(lifecycle, "usb_devices", return_value=present), patch.object(lifecycle, "_virsh", side_effect=virsh):
            return lifecycle.reconcile()

class ReconcileTests(Base):
    def state(self, rep, did="1-2"): return next(i for i in rep["reservations"] if i["device_id"] == did)

    def test_missing_device_is_fixable_even_without_libvirt(self):
        device_manager.reserve("1-2", "qemu:win10")
        with patch.object(lifecycle, "usb_devices", return_value=[]), \
             patch.object(lifecycle, "_virsh", side_effect=RuntimeError("virsh is not installed")):
            rep = lifecycle.reconcile()
        self.assertFalse(rep["libvirt_available"])
        self.assertEqual(self.state(rep)["state"], "device_missing")
        self.assertTrue(self.state(rep)["fixable"])

    def test_active_attachment(self):
        device_manager.reserve("1-2", "qemu:win10")
        rep = self.run_reconcile([DEV], {"win10": "running"}, live={"win10": dom_xml(addr=(1, 5))})
        self.assertEqual(self.state(rep)["state"], "active"); self.assertFalse(self.state(rep)["fixable"])

    def test_running_domain_without_attachment_is_stale(self):
        device_manager.reserve("1-2", "qemu:win10")
        rep = self.run_reconcile([DEV], {"win10": "running"}, live={"win10": dom_xml(addr=(1, 9))})
        self.assertEqual(self.state(rep)["state"], "attach_missing"); self.assertTrue(self.state(rep)["fixable"])

    def test_stopped_domain_keeps_reservation_if_persistent_hostdev(self):
        device_manager.reserve("1-2", "qemu:win10")
        rep = self.run_reconcile([DEV], {"win10": "shut off"}, inactive={"win10": dom_xml(ids=("0x04a9", "0x2709"))})
        self.assertEqual(self.state(rep)["state"], "reserved_for_persistent"); self.assertFalse(self.state(rep)["fixable"])

    def test_stopped_domain_without_hostdev_is_stale(self):
        device_manager.reserve("1-2", "qemu:win10")
        rep = self.run_reconcile([DEV], {"win10": "shut off"})
        self.assertEqual(self.state(rep)["state"], "owner_not_running")

    def test_undefined_domain_is_stale(self):
        device_manager.reserve("1-2", "qemu:ghost")
        rep = self.run_reconcile([DEV], {"win10": "running"})
        self.assertEqual(self.state(rep)["state"], "domain_missing")

    def test_foreign_owner_never_fixable(self):
        device_manager.reserve("1-2", "android")
        rep = self.run_reconcile([], {})
        self.assertEqual(self.state(rep)["state"], "foreign_owner"); self.assertFalse(self.state(rep)["fixable"])

    def test_orphan_attachment_reported(self):
        rep = self.run_reconcile([DEV], {"win10": "running"}, live={"win10": dom_xml(addr=(1, 5))})
        self.assertEqual(rep["orphans"][0]["device_id"], "1-2")
        self.assertIn("unpassthrough", rep["orphans"][0]["suggestion"])

class RecoverTests(Base):
    def test_requires_root(self):
        with patch.object(lifecycle.os, "geteuid", return_value=1000), self.assertRaises(PermissionError):
            lifecycle.recover()

    def test_releases_only_fixable_and_audits(self):
        device_manager.reserve("1-2", "qemu:win10")
        with patch.object(device_manager, "usb_devices", return_value=[DEV, {**DEV, "sysfs_name": "1-3"}]):
            device_manager.reserve("1-3", "android")
        with patch.object(lifecycle.os, "geteuid", return_value=0), \
             patch.object(lifecycle, "reconcile", return_value={"reservations": [
                 {"device_id": "1-2", "owner": "qemu:win10", "state": "device_missing", "fixable": True},
                 {"device_id": "1-3", "owner": "android", "state": "foreign_owner", "fixable": False}], "orphans": []}):
            out = lifecycle.recover()
        self.assertEqual([r["device_id"] for r in out["released"]], ["1-2"])
        self.assertEqual([r["device_id"] for r in device_manager.list_reservations()], ["1-3"])
        self.assertIn("usb_recover_release", (Path(self.tmp.name) / "audit.log").read_text())

class PassthroughSafetyTests(Base):
    def attach(self, attached_result, persistent=False):
        def virsh(args):
            if args[0] == "domstate": return "running"
            if args[0] == "attach-device" and "--live" in args: raise RuntimeError("timeout")
            return ""
        with patch.object(rm, "_assert_root"), patch.object(rm, "_virsh", side_effect=virsh), \
             patch.object(rm, "_find_device", return_value={**DEV, "bus_number": 1, "device_number": 5}), \
             patch.object(rm, "_interfaces", return_value=["07"]), \
             patch.object(lifecycle, "device_attached", return_value=attached_result):
            return rm.passthrough("1-2", "win10", persistent=persistent)

    def test_failed_attach_releases_reservation(self):
        with self.assertRaises(RuntimeError): self.attach(False)
        self.assertEqual(device_manager.list_reservations(), [])

    def test_ambiguous_attach_keeps_reservation(self):
        with self.assertRaisesRegex(RuntimeError, "reservation qemu:win10 was kept"): self.attach(True)
        self.assertEqual(len(device_manager.list_reservations()), 1)

    def test_unknown_state_keeps_reservation(self):
        with self.assertRaises(RuntimeError): self.attach(None)
        self.assertEqual(len(device_manager.list_reservations()), 1)

    def test_persistent_xml_uses_vendor_product(self):
        xml = rm._xml(DEV, by_id=True)
        self.assertIn('id="0x04a9"', xml); self.assertIn('id="0x2709"', xml); self.assertNotIn("address", xml)

    def test_persistent_refused_for_identical_devices(self):
        with patch.object(rm, "usb_devices", return_value=[DEV, {**DEV, "sysfs_name": "1-3"}]), self.assertRaises(ValueError):
            rm._assert_unambiguous(DEV)

if __name__ == "__main__": unittest.main()
