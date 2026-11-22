"""USB inventory, logical device reservations, and udev event history.

Reservations are advisory CFOS ownership records. They do not detach devices,
change permissions, or guarantee kernel-level isolation/passthrough.
"""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
import time
from pathlib import Path
from typing import Optional

from .collector import usb_devices

DB_PATH = os.environ.get("CFOS_DEVICE_DB", "/var/lib/cfos/devices.db")


@contextmanager
def _db():
    db = _connect()
    try:
        with db:
            yield db
    finally:
        db.close()


def _connect() -> sqlite3.Connection:
    path = Path(DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(path), timeout=5.0)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("""CREATE TABLE IF NOT EXISTS reservations (
        device_id TEXT PRIMARY KEY, owner TEXT NOT NULL,
        reserved_at REAL NOT NULL, pid INTEGER NOT NULL
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS device_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT, action TEXT NOT NULL,
        device_id TEXT NOT NULL, vendor_id TEXT, product_id TEXT,
        product TEXT, occurred_at REAL NOT NULL
    )""")
    return db


def device_id(device: dict) -> str:
    return str(device.get("sysfs_name", "")).strip()


def list_devices() -> list[dict]:
    current = usb_devices()
    try:
        with _db() as db:
            reservations = {row[0]: {"owner": row[1], "reserved_at": row[2], "pid": row[3]}
                            for row in db.execute("SELECT device_id, owner, reserved_at, pid FROM reservations")}
    except (OSError, sqlite3.Error):
        # Read-only local diagnostics must remain usable without write access to /var/lib/cfos.
        reservations = {}
    for item in current:
        reservation = reservations.get(device_id(item))
        item["device_id"] = device_id(item)
        item["reservation"] = reservation
        item["available_to_cfos"] = reservation is None
    return current


def list_reservations() -> list[dict]:
    """All advisory reservations, including ones whose device is no longer present."""
    with _db() as db:
        rows = db.execute("SELECT device_id, owner, reserved_at FROM reservations ORDER BY device_id").fetchall()
    return [{"device_id": r[0], "owner": r[1], "reserved_at": r[2]} for r in rows]


def reserve(target: str, owner: str) -> dict:
    target, owner = target.strip(), owner.strip()
    if not target or len(target) > 128:
        raise ValueError("Invalid device identifier")
    if not owner or len(owner) > 64:
        raise ValueError("Owner must contain 1-64 characters")
    devices = {device_id(d): d for d in usb_devices()}
    if target not in devices:
        raise ValueError(f"USB device not currently present: {target}")
    with _db() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT owner FROM reservations WHERE device_id=?", (target,)).fetchone()
        if row:
            if row[0] == owner:
                return {"device_id": target, "owner": owner, "already_reserved": True}
            raise RuntimeError(f"Device is already reserved by: {row[0]}")
        db.execute("INSERT INTO reservations VALUES (?, ?, ?, ?)",
                   (target, owner, time.time(), os.getpid()))
        return {"device_id": target, "owner": owner, "already_reserved": False}


def release(target: str, owner: Optional[str] = None) -> dict:
    target = target.strip()
    if not target:
        raise ValueError("Invalid device identifier")
    with _db() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT owner FROM reservations WHERE device_id=?", (target,)).fetchone()
        if not row:
            raise ValueError(f"Device is not reserved: {target}")
        if owner and row[0] != owner:
            raise PermissionError(f"Device is reserved by {row[0]}, not {owner}")
        db.execute("DELETE FROM reservations WHERE device_id=?", (target,))
        return {"device_id": target, "released": True, "previous_owner": row[0]}


def record_event(action: str, device: dict) -> None:
    target = device.get("sys_name") or device.get("sysfs_name") or "unknown"
    with _db() as db:
        db.execute("INSERT INTO device_events(action, device_id, vendor_id, product_id, product, occurred_at) "
                   "VALUES (?, ?, ?, ?, ?, ?)",
                   (action, target, device.get("id_vendor"), device.get("id_product"),
                    device.get("product"), time.time()))


def recent_events(limit: int = 30) -> list[dict]:
    try:
        with _db() as db:
            rows = db.execute("SELECT action, device_id, vendor_id, product_id, product, occurred_at "
                              "FROM device_events ORDER BY id DESC LIMIT ?", (max(1, min(limit, 100)),)).fetchall()
    except (OSError, sqlite3.Error):
        rows = []
    return [dict(zip(("action", "device_id", "vendor_id", "product_id", "product", "occurred_at"), row))
            for row in rows]
