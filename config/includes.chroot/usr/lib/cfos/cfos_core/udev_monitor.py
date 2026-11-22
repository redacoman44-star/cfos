"""Optional pyudev monitor; absence of pyudev never blocks CFOS startup."""
from __future__ import annotations
import threading
from .device_manager import record_event


def start_udev_monitor() -> threading.Thread | None:
    try:
        import pyudev
    except ImportError:
        return None

    def run():
        try:
            context = pyudev.Context()
            monitor = pyudev.Monitor.from_netlink(context)
            monitor.filter_by(subsystem="usb")
            observer = pyudev.MonitorObserver(monitor, callback=_on_event, name="cfos-udev")
            observer.start()
            # Observer is daemonized; keep a reference through the thread target.
            threading.Event().wait()
        except (OSError, RuntimeError):
            # USB sysfs enumeration remains available if netlink monitoring is unavailable.
            return

    def _on_event(action, device):
        if device.get("DEVTYPE") != "usb_device":
            return
        try:
            record_event(action, {
                "sys_name": device.sys_name,
                "id_vendor": device.get("ID_VENDOR_ID"),
                "id_product": device.get("ID_MODEL_ID"),
                "product": device.get("ID_MODEL"),
            })
        except (OSError, ValueError):
            pass

    thread = threading.Thread(target=run, name="cfos-udev-monitor", daemon=True)
    thread.start()
    return thread
