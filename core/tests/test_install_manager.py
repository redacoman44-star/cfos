import os, tempfile, time, unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
from cfos_core import install_manager as im

SIM_NEW = "Inst firmware-realtek (20240709-2) []\nConf firmware-realtek (20240709-2)\n"
SIM_UPG = "Inst libfoo1 [1.0-1] (1.1-1 Debian:13 [amd64])\nInst foo-driver (2.0-1 Debian:13 [amd64])\n"
SIM_RM = "Inst foo-driver (2.0-1 Debian:13 [amd64])\nRemv old-driver [1.0]\n"

def ok(out): return NS(returncode=0, stdout=out, stderr="")

class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.p = [patch.object(im, "STATE_DIR", Path(self.tmp.name)/"state"),
                  patch.object(im, "AUDIT_LOG", Path(self.tmp.name)/"log"/"audit.log")]
        for x in self.p: x.start()
    def tearDown(self):
        for x in self.p: x.stop()
        self.tmp.cleanup()

class PlanTests(Base):
    def test_plan_parses_and_changes_nothing(self):
        with patch.object(im, "_apt", return_value=ok(SIM_NEW)) as apt:
            plan = im.plan("firmware-realtek")
        self.assertEqual(apt.call_args[0][0][0], "-s")
        self.assertEqual(plan["firmware_packages"], ["firmware-realtek"])
        self.assertTrue(plan["approved_to_apply"])
        self.assertEqual(plan["status"], "planned")

    def test_removals_block_plan(self):
        with patch.object(im, "_apt", return_value=ok(SIM_RM)):
            plan = im.plan("foo-driver")
        self.assertFalse(plan["approved_to_apply"])
        self.assertIn("would remove old-driver", plan["blocked_reasons"])

    def test_invalid_and_protected_names_rejected(self):
        for bad in ["", "Foo", "a;rm -rf /", "../x", "x" * 200]:
            with self.assertRaises(ValueError): im.plan(bad)
        with self.assertRaises(ValueError): im.plan("systemd")
        with self.assertRaises(ValueError): im.plan("linux-image-amd64")

    def test_apt_failure_is_reported(self):
        with patch.object(im, "_apt", return_value=NS(returncode=100, stdout="", stderr="E: Unable to locate package zzz")):
            with self.assertRaises(ValueError): im.plan("zzz")

class ApplyTests(Base):
    def make(self, sim=SIM_UPG):
        with patch.object(im, "_apt", return_value=ok(sim)):
            return im.plan("foo-driver")

    def test_requires_root(self):
        plan = self.make()
        with patch.object(im.os, "geteuid", return_value=1000), self.assertRaises(PermissionError):
            im.apply(plan["plan_id"], plan["plan_id"])

    def test_wrong_approval_refused_and_nothing_run(self):
        plan = self.make()
        with patch.object(im.os, "geteuid", return_value=0), patch.object(im, "_apt") as apt:
            with self.assertRaises(PermissionError): im.apply(plan["plan_id"], "000000000000")
            apt.assert_not_called()

    def test_apply_success_audits_and_marks_applied(self):
        plan = self.make()
        calls = []
        def fake(args, timeout=900):
            calls.append(args); return ok(SIM_UPG)
        with patch.object(im.os, "geteuid", return_value=0), patch.object(im, "_apt", side_effect=fake), \
             patch.object(im, "_installed_version", return_value="2.0-1"):
            out = im.apply(plan["plan_id"], plan["plan_id"], offline=True)
        self.assertEqual(out["status"], "applied")
        install = calls[-1]
        self.assertEqual(install[:3], ["install", "-y", "--no-install-recommends"])
        self.assertIn("--no-download", install)
        self.assertEqual(im._load(plan["plan_id"])["status"], "applied")
        self.assertIn("apply_done", im.AUDIT_LOG.read_text())

    def test_state_change_aborts(self):
        plan = self.make()
        with patch.object(im.os, "geteuid", return_value=0), patch.object(im, "_apt", return_value=ok(SIM_NEW)):
            with self.assertRaises(RuntimeError): im.apply(plan["plan_id"], plan["plan_id"])

    def test_expired_plan_refused(self):
        plan = self.make()
        stored = im._load(plan["plan_id"]); stored["expires_at"] = time.time() - 1; im._save(stored)
        with patch.object(im.os, "geteuid", return_value=0), self.assertRaises(ValueError):
            im.apply(plan["plan_id"], plan["plan_id"])

    def test_blocked_plan_refused(self):
        plan = self.make(SIM_RM)
        with patch.object(im.os, "geteuid", return_value=0), self.assertRaises(PermissionError):
            im.apply(plan["plan_id"], plan["plan_id"])

    def test_failed_install_marked_failed(self):
        plan = self.make()
        def fake(args, timeout=900):
            return ok(SIM_UPG) if args[0] == "-s" else NS(returncode=100, stdout="", stderr="E: boom")
        with patch.object(im.os, "geteuid", return_value=0), patch.object(im, "_apt", side_effect=fake), \
             patch.object(im, "_installed_version", return_value=None):
            with self.assertRaises(RuntimeError): im.apply(plan["plan_id"], plan["plan_id"])
        self.assertEqual(im._load(plan["plan_id"])["status"], "failed")

class RollbackTests(Base):
    def test_rollback_removes_new_and_downgrades_old(self):
        with patch.object(im, "_apt", return_value=ok(SIM_UPG)):
            plan = im.plan("foo-driver")
        stored = im._load(plan["plan_id"]); stored["status"] = "applied"; im._save(stored)
        calls = []
        def fake(args, timeout=900): calls.append(args); return ok("")
        with patch.object(im.os, "geteuid", return_value=0), patch.object(im, "_apt", side_effect=fake):
            out = im.rollback(plan["plan_id"], plan["plan_id"])
        self.assertEqual(out["removed"], ["foo-driver"])
        self.assertEqual(out["restored"], ["libfoo1=1.0-1"])
        self.assertEqual(calls[0], ["remove", "-y", "foo-driver"])
        self.assertIn("--allow-downgrades", calls[1])

    def test_rollback_of_unapplied_plan_refused(self):
        with patch.object(im, "_apt", return_value=ok(SIM_NEW)):
            plan = im.plan("firmware-realtek")
        with patch.object(im.os, "geteuid", return_value=0), self.assertRaises(ValueError):
            im.rollback(plan["plan_id"], plan["plan_id"])

class PlanIdTests(unittest.TestCase):
    def test_plan_id_is_path_safe(self):
        for bad in ["../../etc/passwd", "ABC", "", "123"]:
            with self.assertRaises(ValueError): im._plan_path(bad)

if __name__ == "__main__": unittest.main()
