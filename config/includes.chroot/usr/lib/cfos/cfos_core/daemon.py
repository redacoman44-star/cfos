"""Small read-only Unix-socket API for CFOS Core."""
from __future__ import annotations
import json
import os
import signal
import socket
import socketserver
import threading
from pathlib import Path
from .collector import collect
from .udev_monitor import start_udev_monitor

SOCKET_PATH = os.environ.get("CFOS_SOCKET", "/run/cfos/core.sock")
ALLOWED = {"status", "resources", "devices", "sessions", "events", "reserve", "release", "hardware", "profile", "drivers", "driver"}


class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        raw = self.rfile.readline(4097)
        try:
            if len(raw) > 4096 or not raw.endswith(b"\n"):
                raise ValueError("Request too large or incomplete")
            request = json.loads(raw.decode("utf-8"))
            command = request.get("command") if isinstance(request, dict) else None
            if command not in ALLOWED:
                raise ValueError("Invalid command")
            if command in {"reserve", "release"}:
                device = request.get("device", "")
                owner = request.get("owner")
                if not isinstance(device, str) or not isinstance(owner, str) or not owner:
                    raise ValueError("Device and owner must be strings")
            if command in {"profile", "driver"} and not isinstance(request.get("device", ""), str):
                raise ValueError("Device must be a string")
            response = {"ok": True, "data": collect(command, device=request.get("device", ""), owner=request.get("owner"))}
        except Exception as exc:
            response = {"ok": False, "error": str(exc)}
        self.wfile.write((json.dumps(response, ensure_ascii=False) + "\n").encode())


class Server(socketserver.ThreadingUnixStreamServer):
    daemon_threads = True
    allow_reuse_address = True


def main():
    path = Path(SOCKET_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.unlink()
    except FileNotFoundError:
        pass
    start_udev_monitor()
    with Server(str(path), Handler) as server:
        os.chmod(path, 0o660)
        def stop(_sig, _frame):
            threading.Thread(target=server.shutdown, daemon=True).start()
        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGINT, stop)
        try:
            server.serve_forever(poll_interval=0.5)
        finally:
            path.unlink(missing_ok=True)

if __name__ == "__main__":
    main()
