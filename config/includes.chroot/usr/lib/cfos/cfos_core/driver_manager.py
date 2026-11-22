"""Read-only Linux driver intelligence; never installs or loads drivers."""
from __future__ import annotations
import re
import shutil
import subprocess
from pathlib import Path
from .collector import usb_devices, bound_driver
from .hardware_profiles import pci_devices

RUN = subprocess.run

def _run(args: list[str], timeout: int = 8) -> str:
    try:
        result = RUN(args, check=False, capture_output=True, text=True, timeout=timeout)
        return result.stdout.strip() if result.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""

def _module_candidates(modalias: str) -> list[str]:
    if not modalias or not shutil.which("modprobe"):
        return []
    output = _run(["modprobe", "--resolve-alias", modalias])
    return sorted({line.strip() for line in output.splitlines() if re.fullmatch(r"[A-Za-z0-9_+-]{1,128}", line.strip())})

def _module_details(module: str) -> dict:
    loaded = Path("/sys/module") / module.replace("-", "_")
    filename = _run(["modinfo", "-F", "filename", module]) if shutil.which("modinfo") else ""
    package = None
    if filename and shutil.which("dpkg-query"):
        owner = _run(["dpkg-query", "-S", filename])
        if owner:
            package = owner.split(":", 1)[0].split(",", 1)[0].strip()
    candidate = None
    if package and shutil.which("apt-cache"):
        policy = _run(["apt-cache", "policy", package])
        match = re.search(r"Candidate:\s*(\S+)", policy)
        if match and match.group(1) != "(none)":
            candidate = match.group(1)
    return {
        "module": module,
        "loaded": loaded.exists(),
        "module_file": filename or None,
        "installed_package": package,
        "repository_candidate": candidate,
        "package_status": "installed" if package else ("module_file_found" if filename else "unknown"),
    }

def _inspect(bus: str, device_id: str, modalias: str, bound_driver: str | None) -> dict:
    modules = _module_candidates(modalias)
    details = [_module_details(module) for module in modules[:12]]
    if bound_driver:
        state = "driver_bound"
    elif modules:
        state = "matching_module_available"
    elif modalias:
        state = "no_matching_module_found"
    else:
        state = "modalias_unavailable"
    return {
        "device_id": device_id, "bus": bus, "modalias": modalias or None,
        "bound_driver": bound_driver,
        "candidate_modules": details,
        "driver_state": state,
        "recommendation": (
            "No action needed; a kernel driver is bound." if bound_driver else
            "Review candidate modules and Debian package availability before installation." if details else
            "Check hardware IDs, firmware requirements, and Debian 13 support; no automatic install is proposed."
        ),
        "installation_performed": False,
    }

def inspect_device(device_id: str) -> dict:
    device_id = device_id.strip()
    if not device_id:
        raise ValueError("A USB sysfs ID or PCI address is required")
    for item in usb_devices():
        if item.get("sysfs_name") == device_id:
            bound = bound_driver(Path("/sys/bus/usb/devices") / device_id)
            return _inspect("USB", device_id, item.get("modalias", ""), bound)
    for item in pci_devices():
        if item.get("device_id") == device_id:
            return _inspect("PCI", device_id, item.get("modalias", ""), item.get("kernel_driver"))
    raise ValueError(f"Hardware device not found: {device_id}")

def driver_report() -> dict:
    devices = []
    for item in usb_devices():
        bound = bound_driver(Path("/sys/bus/usb/devices") / item["sysfs_name"])
        devices.append(_inspect("USB", item["sysfs_name"], item.get("modalias", ""), bound))
    for item in pci_devices():
        devices.append(_inspect("PCI", item["device_id"], item.get("modalias", ""), item.get("kernel_driver")))
    return {
        "devices": devices,
        "summary": {
            "device_count": len(devices),
            "driver_bound": sum(d["driver_state"] == "driver_bound" for d in devices),
            "matching_module_available": sum(d["driver_state"] == "matching_module_available" for d in devices),
            "no_matching_module_found": sum(d["driver_state"] == "no_matching_module_found" for d in devices),
            "installation_performed": False,
        },
        "limitations": [
            "Module alias resolution depends on the host's installed kernel modules.alias database.",
            "Package ownership and apt candidate data are local-cache observations, not proof of hardware compatibility.",
            "Firmware may be required even when a kernel module is available.",
            "No package installation, module loading, firmware download, or network access is performed."
        ]
    }
