"""CFOS command line client."""
from __future__ import annotations
import argparse
import json
import socket
import sys
from .collector import collect

DEFAULT_SOCKET = "/run/cfos/core.sock"


def main(argv=None):
    parser = argparse.ArgumentParser(prog="cfos", description="CFOS host diagnostics")
    parser.add_argument("command", choices=["status", "resources", "devices", "sessions", "events", "reserve", "release", "passthrough", "unpassthrough", "hardware", "profile", "drivers", "driver", "driver-plan", "driver-apply", "driver-rollback", "usb-reconcile", "usb-recover"])
    parser.add_argument("--socket", default=DEFAULT_SOCKET, help="CFOS Core Unix socket")
    parser.add_argument("--local", action="store_true", help="Collect locally without the daemon")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    parser.add_argument("--device", help="USB sysfs identifier, e.g. 1-2")
    parser.add_argument("--owner", help="CFOS runtime name that owns the reservation")
    parser.add_argument("--domain", help="libvirt/QEMU domain name for USB passthrough")
    parser.add_argument("--persistent", action="store_true", help="also change persistent domain XML")
    parser.add_argument("--allow-vendor-specific", action="store_true", help="explicitly permit USB interface class ff")
    parser.add_argument("--package", help="Debian package to plan (driver-plan)")
    parser.add_argument("--plan", help="plan id (driver-apply / driver-rollback)")
    parser.add_argument("--approve", help="repeat the plan id to approve the operation")
    parser.add_argument("--offline", action="store_true", help="apply using only already-downloaded packages")
    args = parser.parse_args(argv)
    try:
        if args.command in {"reserve", "release", "profile", "driver"} and not args.device:
            parser.error("reserve/release requires --device")
        if args.command in {"reserve", "release"} and not args.owner:
            parser.error("reserve/release requires --owner")
        if args.command in {"usb-reconcile", "usb-recover"}:
            if not args.local:
                parser.error("usb-reconcile/usb-recover inspect libvirt and must use --local (recover via sudo)")
            from . import lifecycle
            data = lifecycle.reconcile() if args.command == "usb-reconcile" else lifecycle.recover()
            if args.json:
                print(json.dumps(data, indent=2, ensure_ascii=False))
            elif args.command == "usb-reconcile":
                print(f"libvirt available: {data['libvirt_available']}")
                for k, v in data["summary"].items(): print(f"{k}: {v}")
                for i in data["reservations"]:
                    print(f"- {i['device_id']} [{i['owner']}]: {i['state']}{' (fixable)' if i['fixable'] else ''} - {i['detail']}")
                for o in data["orphans"]:
                    print(f"- {o['device_id']} attached to {o['domain']} without reservation: {o['suggestion']}")
            else:
                print(f"released: {len(data['released'])}")
                for r in data["released"]: print(f"- {r['device_id']} [{r['owner']}] ({r['reason']})")
                for o in data["orphans_not_modified"]: print(f"- orphan not modified: {o['device_id']} on {o['domain']}")
            return 0
        if args.command in {"driver-plan", "driver-apply", "driver-rollback"}:
            if not args.local:
                parser.error("driver install operations are privileged and must use --local (apply/rollback via sudo)")
            from . import install_manager as im
            if args.command == "driver-plan":
                package = args.package
                if not package:
                    if not args.device:
                        parser.error("driver-plan requires --package or --device")
                    found = im.plan_from_device(args.device)
                    if len(found) != 1:
                        raise ValueError("Device maps to " + (", ".join(found) if found else "no installable package")
                                         + "; pass --package explicitly")
                    package = found[0]
                data = im.plan(package, args.device)
            else:
                if not args.plan or not args.approve:
                    parser.error(f"{args.command} requires --plan and --approve (repeat the plan id)")
                data = (im.apply(args.plan, args.approve, offline=args.offline) if args.command == "driver-apply"
                        else im.rollback(args.plan, args.approve))
            print(json.dumps(data, indent=2, ensure_ascii=False))
            return 0
        if args.command in {"passthrough", "unpassthrough"}:
            if not args.device or not args.domain:
                parser.error("passthrough/unpassthrough requires --device and --domain")
            if not args.local:
                parser.error("passthrough operations are privileged and must use --local (typically with sudo)")
            from . import runtime_manager
            if args.command == "passthrough":
                data = runtime_manager.passthrough(args.device, args.domain,
                    persistent=args.persistent, allow_vendor_specific=args.allow_vendor_specific)
            else:
                data = runtime_manager.unpassthrough(args.device, args.domain,
                    persistent=args.persistent)
        elif args.local:
            data = collect(args.command, device=args.device, owner=args.owner)
        else:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                client.settimeout(3.0)
                client.connect(args.socket)
                client.sendall((json.dumps({"command": args.command, "device": args.device, "owner": args.owner}) + "\n").encode())
                stream = client.makefile("r", encoding="utf-8")
                response = json.loads(stream.readline())
            if not response.get("ok"):
                raise RuntimeError(response.get("error", "Unknown daemon error"))
            data = response["data"]
        if args.json:
            print(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            _print_human(args.command, data)
        return 0
    except (OSError, RuntimeError, ValueError, PermissionError, json.JSONDecodeError) as exc:
        print(f"cfos: {exc}", file=sys.stderr)
        if not args.local:
            print("Tip: use --local for direct read-only diagnostics.", file=sys.stderr)
        return 1


def _bytes(value):
    units = ["B", "KiB", "MiB", "GiB", "TiB"]
    amount = float(value)
    for unit in units:
        if amount < 1024 or unit == units[-1]:
            return f"{amount:.1f} {unit}"
        amount /= 1024


def _print_human(command, data):
    if command == "status":
        for key, value in data.items(): print(f"{key}: {value}")
    elif command == "resources":
        print(f"CPU threads: {data['cpu_count']}")
        print(f"Load average: {', '.join(map(str, data['load_average'])) or 'unavailable'}")
        for key, label in [("memory_total_bytes", "RAM total"), ("memory_used_bytes", "RAM used"),
                           ("memory_available_bytes", "RAM available"), ("swap_total_bytes", "Swap total")]:
            print(f"{label}: {_bytes(data.get(key, 0))}")
    elif command == "devices":
        items = data.get("usb", [])
        print(f"USB devices: {len(items)}")
        for item in items:
            name = item.get("product") or item.get("manufacturer") or "Unknown device"
            reservation = item.get("reservation")
            state = f"reserved by {reservation['owner']}" if reservation else "available"
            print(f"- {name} [{item['vendor_id']}:{item['product_id']}] ({item['sysfs_name']}) - {state}")
    elif command == "sessions":
        items = data.get("sessions", [])
        print(f"Detected session processes: {len(items)}")
        for item in items: print(f"- {item['name']} PID={item['pid']} UID={item['uid']}")
    elif command == "hardware":
        summary = data.get("summary", {})
        print("Hardware inventory")
        for key, value in summary.items(): print(f"{key}: {value}")
        for bus in ("usb", "pci"):
            for item in data.get(bus, []):
                name = item.get("model_name") or item.get("vendor_name") or "Unknown device"
                function = item.get("function") or item.get("category")
                print(f"- {bus.upper()} {item['device_id']}: {name} ({function}), driver={item.get('kernel_driver') or 'none'}")
    elif command == "profile":
        print(json.dumps(data.get("profile", {}), indent=2, ensure_ascii=False))
    elif command == "drivers":
        print("Driver intelligence report")
        for key, value in data.get("summary", {}).items(): print(f"{key}: {value}")
        for item in data.get("devices", []):
            print(f"- {item['bus']} {item['device_id']}: {item['driver_state']} "
                  f"(bound={item.get('bound_driver') or 'none'}, candidates={len(item.get('candidate_modules', []))})")
    elif command == "driver":
        print(json.dumps(data.get("driver", {}), indent=2, ensure_ascii=False))
    elif command == "events":
        for item in data.get("events", []):
            print(f"- {item['action']} {item['device_id']} {item.get('vendor_id') or ''}:{item.get('product_id') or ''}")
    elif command in {"reserve", "release", "passthrough", "unpassthrough"}:
        print(json.dumps(data, ensure_ascii=False))

if __name__ == "__main__":
    raise SystemExit(main())
