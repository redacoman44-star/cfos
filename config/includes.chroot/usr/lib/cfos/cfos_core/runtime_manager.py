"""Explicit, opt-in USB passthrough to libvirt/QEMU domains.

This module never shells out through a command interpreter. It uses libvirt's
managed USB hostdev support and a conservative interface-class allowlist.
It is intentionally not exposed through the privileged CFOS daemon socket.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Callable

from . import device_manager
from .collector import usb_devices

RUN = subprocess.run

# USB interface classes: printer (07) and imaging (06). Vendor-specific (ff)
# devices are deliberately excluded by default because they may expose unusual
# functions. HID (03), hubs (09), mass storage (08), and unknown devices are blocked.
ALLOWED_CLASSES = {"06", "07"}


def _interfaces(sysfs_name: str) -> list[str]:
    root = Path("/sys/bus/usb/devices") / sysfs_name
    classes: list[str] = []
    try:
        for interface in root.glob(f"{sysfs_name}:*"):
            value = (interface / "bInterfaceClass").read_text().strip().lower()
            if value:
                classes.append(value.zfill(2))
    except OSError:
        pass
    return classes


def _find_device(target: str) -> dict:
    matches = [d for d in usb_devices() if d.get("sysfs_name") == target]
    if not matches:
        raise ValueError(f"USB device not currently present: {target}")
    item = matches[0]
    try:
        item["bus_number"] = int(item.get("bus_number", ""))
        item["device_number"] = int(item.get("device_number", ""))
    except (TypeError, ValueError):
        raise ValueError("USB bus/device address is unavailable; reconnect the device")
    if not (1 <= item["bus_number"] <= 255 and 1 <= item["device_number"] <= 255):
        raise ValueError("USB bus/device address is invalid")
    return item


def _xml(device: dict, by_id: bool = False) -> str:
    """hostdev XML. Live changes use the current bus/device address; persistent
    (--config) changes use vendor/product IDs because bus/device numbers change
    on every replug or reboot."""
    root = ET.Element("hostdev", {"mode": "subsystem", "type": "usb", "managed": "yes"})
    source = ET.SubElement(root, "source")
    if by_id:
        ET.SubElement(source, "vendor", {"id": "0x" + str(device["vendor_id"]).lower().zfill(4)})
        ET.SubElement(source, "product", {"id": "0x" + str(device["product_id"]).lower().zfill(4)})
    else:
        ET.SubElement(source, "address", {
            "bus": str(device["bus_number"]),
            "device": str(device["device_number"]),
        })
    return ET.tostring(root, encoding="unicode")


def _virsh_with_xml(verb: str, domain: str, xml: str, scope: str) -> None:
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".xml", delete=False) as handle:
        handle.write(xml)
        xml_path = handle.name
    try:
        _virsh([verb, domain, "--file", xml_path, scope])
    finally:
        Path(xml_path).unlink(missing_ok=True)


def _assert_unambiguous(device: dict) -> None:
    same = [d for d in usb_devices()
            if d.get("vendor_id") == device.get("vendor_id") and d.get("product_id") == device.get("product_id")]
    if len(same) > 1:
        raise ValueError("Persistent passthrough is ambiguous: several identical USB devices (same "
                         "vendor/product) are connected. Disconnect the others or use live passthrough only.")


def _virsh(args: list[str]) -> str:
    try:
        result = RUN(["virsh", *args], check=True, capture_output=True, text=True, timeout=20)
    except FileNotFoundError as exc:
        raise RuntimeError("virsh is not installed; install libvirt-clients") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("libvirt command timed out") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "libvirt command failed").strip()
        raise RuntimeError(detail[:500]) from exc
    return result.stdout.strip()


def _assert_root() -> None:
    if os.geteuid() != 0:
        raise PermissionError("USB passthrough changes host device ownership; run this command with sudo")


def passthrough(target: str, domain: str, *, persistent: bool = False,
                allow_vendor_specific: bool = False) -> dict:
    """Attach one approved physical USB device to a running libvirt domain."""
    _assert_root()
    target, domain = target.strip(), domain.strip()
    if not target or not domain or len(domain) > 128 or any(c.isspace() for c in domain):
        raise ValueError("A valid USB device ID and libvirt domain name are required")
    device = _find_device(target)
    classes = _interfaces(target)
    allowed = ALLOWED_CLASSES | ({"ff"} if allow_vendor_specific else set())
    if not classes or any(code not in allowed for code in classes):
        raise PermissionError(
            "USB passthrough blocked by CFOS policy. Allowed interface classes: "
            + ", ".join(sorted(allowed))
            + ". HID, hubs, storage, unknown and mixed-class devices are blocked."
        )

    state = _virsh(["domstate", domain]).lower()
    if "running" not in state:
        raise RuntimeError(f"Domain must be running for live passthrough (state: {state or 'unknown'})")

    if persistent:
        _assert_unambiguous(device)
    owner = f"qemu:{domain}"
    device_manager.reserve(target, owner)
    try:
        _virsh_with_xml("attach-device", domain, _xml(device), "--live")
    except Exception as exc:
        from . import lifecycle
        attached = lifecycle.device_attached(domain, device)
        if attached is False:
            # Attach definitely did not happen: do not leave a stale CFOS reservation.
            try:
                device_manager.release(target, owner)
            except Exception:
                pass
            raise
        raise RuntimeError(
            "attach reported an error but the device "
            + ("appears attached" if attached else "state could not be verified")
            + f"; reservation {owner} was kept. Run: sudo cfos usb-reconcile --local") from exc
    if persistent:
        try:
            _virsh_with_xml("attach-device", domain, _xml(device, by_id=True), "--config")
        except Exception as exc:
            raise RuntimeError("device is attached live (reservation kept) but the persistent domain "
                               f"definition could not be updated: {exc}") from exc
    return {"device_id": target, "domain": domain, "attached": True,
            "persistent": persistent, "interface_classes": classes,
            "vendor_id": device.get("vendor_id"), "product_id": device.get("product_id")}


def unpassthrough(target: str, domain: str, *, persistent: bool = False) -> dict:
    """Detach a previously attached device; release its reservation on success."""
    _assert_root()
    target, domain = target.strip(), domain.strip()
    if not target or not domain or len(domain) > 128 or any(c.isspace() for c in domain):
        raise ValueError("A valid USB device ID and libvirt domain name are required")
    device = _find_device(target)
    owner = f"qemu:{domain}"
    _virsh_with_xml("detach-device", domain, _xml(device), "--live")
    if persistent:
        _virsh_with_xml("detach-device", domain, _xml(device, by_id=True), "--config")
    device_manager.release(target, owner)
    return {"device_id": target, "domain": domain, "detached": True,
            "reservation_released": True, "persistent": persistent}
