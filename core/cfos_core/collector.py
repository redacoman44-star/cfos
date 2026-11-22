"""Read-only Linux host information collectors; standard library only."""
from __future__ import annotations
import os
import platform
import re
from pathlib import Path


def _read(path: str, default: str = "") -> str:
    try:
        return Path(path).read_text(errors="replace").strip()
    except (OSError, PermissionError):
        return default


def bound_driver(device_path) -> str | None:
    """Return the kernel driver bound to a sysfs device, or None.

    Path.resolve() is non-strict, so a missing 'driver' symlink would resolve to
    the literal path and yield the bogus name 'driver'. Check for the symlink first.
    """
    link = Path(device_path) / "driver"
    try:
        if not link.is_symlink():
            return None
        return Path(os.path.realpath(link)).name or None
    except OSError:
        return None


def _meminfo() -> dict[str, int]:
    values: dict[str, int] = {}
    for line in _read("/proc/meminfo").splitlines():
        match = re.match(r"^(MemTotal|MemAvailable|SwapTotal|SwapFree):\s+(\d+)", line)
        if match:
            values[match.group(1)] = int(match.group(2)) * 1024
    total = values.get("MemTotal", 0)
    available = values.get("MemAvailable", 0)
    return {
        "memory_total_bytes": total,
        "memory_available_bytes": available,
        "memory_used_bytes": max(total - available, 0),
        "swap_total_bytes": values.get("SwapTotal", 0),
        "swap_free_bytes": values.get("SwapFree", 0),
    }


def _cpu_count() -> int:
    return os.cpu_count() or 0


def resources() -> dict:
    load = _read("/proc/loadavg").split()
    try:
        load_avg = [float(v) for v in load[:3]]
    except ValueError:
        load_avg = []
    result = {"cpu_count": _cpu_count(), "load_average": load_avg}
    result.update(_meminfo())
    return result


def usb_devices() -> list[dict]:
    devices: list[dict] = []
    root = Path("/sys/bus/usb/devices")
    try:
        entries = sorted(root.iterdir(), key=lambda p: p.name)
    except OSError:
        return devices
    for entry in entries:
        if not (entry / "idVendor").exists() or not (entry / "idProduct").exists():
            continue
        item = {
            "sysfs_name": entry.name,
            "vendor_id": _read(str(entry / "idVendor")),
            "product_id": _read(str(entry / "idProduct")),
            "manufacturer": _read(str(entry / "manufacturer")),
            "product": _read(str(entry / "product")),
            "serial": _read(str(entry / "serial")),
            "bus_number": _read(str(entry / "busnum")),
            "device_number": _read(str(entry / "devnum")),
            "modalias": _read(str(entry / "modalias")),
        }
        devices.append(item)
    return devices


def sessions() -> list[dict]:
    """Return processes that look like login/session leaders, without user data."""
    found: list[dict] = []
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit():
            continue
        try:
            status = (proc / "status").read_text(errors="replace")
            fields = dict(line.split(":", 1) for line in status.splitlines() if ":" in line)
            comm = (proc / "comm").read_text(errors="replace").strip()
            if comm in {"systemd", "greetd", "labwc", "gnome-session", "plasmashell"}:
                found.append({"pid": int(proc.name), "name": comm,
                              "uid": fields.get("Uid", "").strip().split()[0] if fields.get("Uid") else ""})
        except (OSError, ValueError, IndexError):
            continue
    return found


def status() -> dict:
    return {
        "name": "CFOS Core",
        "version": "0.8.0",
        "host_os": platform.system(),
        "host_release": platform.release(),
        "architecture": platform.machine(),
        "python": platform.python_version(),
    }


def collect(command: str, **kwargs) -> dict:
    from . import device_manager
    handlers = {
        "status": status,
        "resources": resources,
        "devices": lambda: {"usb": device_manager.list_devices()},
        "sessions": lambda: {"sessions": sessions()},
        "events": lambda: {"events": device_manager.recent_events()},
        "hardware": lambda: __import__("cfos_core.hardware_profiles", fromlist=["hardware_inventory"]).hardware_inventory(),
        "drivers": lambda: __import__("cfos_core.driver_manager", fromlist=["driver_report"]).driver_report(),
    }
    if command == "profile":
        from .hardware_profiles import profile_usb
        return {"profile": profile_usb(kwargs.get("device", ""))}
    if command == "driver":
        from .driver_manager import inspect_device
        return {"driver": inspect_device(kwargs.get("device", ""))}
    if command == "reserve":
        return device_manager.reserve(kwargs.get("device", ""), kwargs.get("owner", ""))
    if command == "release":
        return device_manager.release(kwargs.get("device", ""), kwargs.get("owner"))
    if command not in handlers:
        raise ValueError(f"Unsupported command: {command}")
    return handlers[command]()
