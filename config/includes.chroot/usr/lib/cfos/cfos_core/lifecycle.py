"""USB reservation lifecycle: reconcile CFOS reservations with reality and recover stale ones.

reconcile() is read-only. recover() (root, local only) releases only reservations that are
provably stale and only CFOS-owned ('qemu:<domain>') ones. It never detaches devices and
never edits libvirt domain definitions; orphan attachments are reported with a suggested command.
"""
from __future__ import annotations
import os
import xml.etree.ElementTree as ET

from . import device_manager
from .collector import usb_devices
from .install_manager import _audit
from .runtime_manager import _virsh


def _hostdevs(domain: str, inactive: bool = False) -> list[dict]:
    args = ["dumpxml"] + (["--inactive"] if inactive else []) + [domain]
    root = ET.fromstring(_virsh(args))
    found = []
    for hd in root.iterfind("./devices/hostdev"):
        if hd.get("type") != "usb":
            continue
        src = hd.find("source")
        if src is None:
            continue
        item = {}
        addr, ven, prod = src.find("address"), src.find("vendor"), src.find("product")
        if addr is not None:
            item["bus"], item["device"] = _int(addr.get("bus")), _int(addr.get("device"))
        if ven is not None and prod is not None:
            item["vendor"], item["product"] = _int(ven.get("id")), _int(prod.get("id"))
        found.append(item)
    return found


def _int(value):
    try:
        return int(str(value), 0)
    except (TypeError, ValueError):
        return None


def _matches(hostdev: dict, device: dict) -> bool:
    if hostdev.get("bus") is not None and hostdev.get("device") is not None:
        return (hostdev["bus"], hostdev["device"]) == (_int(device.get("bus_number")), _int(device.get("device_number")))
    return (hostdev.get("vendor"), hostdev.get("product")) == (_int("0x" + str(device.get("vendor_id", ""))),
                                                              _int("0x" + str(device.get("product_id", ""))))


def device_attached(domain: str, device: dict):
    """True/False if libvirt says the device is/is not attached live; None if unknown."""
    try:
        return any(_matches(h, device) for h in _hostdevs(domain))
    except (RuntimeError, ET.ParseError):
        return None


def _domains() -> dict[str, str]:
    names = [n.strip() for n in _virsh(["list", "--all", "--name"]).splitlines() if n.strip()]
    return {n: _virsh(["domstate", n]).lower() for n in names}


def reconcile() -> dict:
    present = {d["sysfs_name"]: d for d in usb_devices()}
    reservations = device_manager.list_reservations()
    try:
        domains, libvirt = _domains(), True
    except RuntimeError:
        domains, libvirt = {}, False
    live: dict[str, list] = {}
    persistent: dict[str, list] = {}
    if libvirt:
        for name, state in domains.items():
            try:
                if "running" in state:
                    live[name] = _hostdevs(name)
                persistent[name] = _hostdevs(name, inactive=True)
            except (RuntimeError, ET.ParseError):
                live.pop(name, None)
    items = []
    reserved_ids = set()
    for r in reservations:
        did, owner = r["device_id"], r["owner"]
        reserved_ids.add(did)
        entry = {"device_id": did, "owner": owner, "fixable": False}
        device = present.get(did)
        if not owner.startswith("qemu:"):
            entry.update(state="foreign_owner", detail="Not a CFOS/qemu reservation; never modified automatically")
        elif device is None:
            entry.update(state="device_missing", fixable=True,
                         detail="Device is no longer present; the reservation is stale")
        elif not libvirt:
            entry.update(state="unverifiable", detail="libvirt is unavailable; cannot verify the domain")
        else:
            dom = owner.split(":", 1)[1]
            if dom not in domains:
                entry.update(state="domain_missing", fixable=True, detail=f"Domain {dom} is not defined")
            elif dom in live:
                if any(_matches(h, device) for h in live[dom]):
                    entry.update(state="active", detail="Device is attached to the running domain")
                else:
                    entry.update(state="attach_missing", fixable=True,
                                 detail="Domain is running but the device is not attached to it")
            elif any(_matches(h, device) for h in persistent.get(dom, [])):
                entry.update(state="reserved_for_persistent",
                             detail="Domain is not running; the device is in its persistent definition")
            elif "running" in domains[dom]:
                entry.update(state="unverifiable", detail="Could not read the running domain definition")
            else:
                entry.update(state="owner_not_running", fixable=True,
                             detail=f"Domain {dom} is not running and the device is not in its definition")
        items.append(entry)
    orphans = []
    for dom, hostdevs in live.items():
        for did, device in present.items():
            if did not in reserved_ids and any(_matches(h, device) for h in hostdevs):
                orphans.append({"device_id": did, "domain": dom, "state": "orphan_attach", "suggestion":
                                f"sudo cfos unpassthrough --local --device {did} --domain {dom}  "
                                f"(or reserve it: cfos reserve --device {did} --owner qemu:{dom})"})
    return {"libvirt_available": libvirt, "reservations": items, "orphans": orphans,
            "summary": {"reservations": len(items), "fixable": sum(i["fixable"] for i in items),
                        "orphans": len(orphans)}}


def recover() -> dict:
    if os.geteuid() != 0:
        raise PermissionError("Recovery changes reservations; run with sudo and --local")
    report = reconcile()
    released = []
    for item in report["reservations"]:
        if not item["fixable"]:
            continue
        try:
            device_manager.release(item["device_id"], item["owner"])
            released.append({"device_id": item["device_id"], "owner": item["owner"], "reason": item["state"]})
            _audit("usb_recover_release", device_id=item["device_id"], owner=item["owner"], reason=item["state"])
        except (ValueError, PermissionError):
            continue  # already released or changed owner meanwhile; leave it
    return {"released": released, "orphans_not_modified": report["orphans"],
            "left_unchanged": [i for i in report["reservations"] if not i["fixable"]]}
