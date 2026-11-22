"""Approval-gated driver/firmware package installation (plan -> apply -> rollback).

Nothing is changed by plan(). apply() and rollback() need root, run locally only
(never through the daemon socket), and require the technician to repeat the exact
plan id as approval. Every step is written to an audit log.
"""
from __future__ import annotations
import hashlib
import json
import os
import re
import subprocess
import time
import uuid
from pathlib import Path

RUN = subprocess.run
STATE_DIR = Path(os.environ.get("CFOS_STATE_DIR", "/var/lib/cfos"))
AUDIT_LOG = Path(os.environ.get("CFOS_AUDIT_LOG", "/var/log/cfos/audit.log"))
PLAN_TTL = 15 * 60
PKG_RE = re.compile(r"[a-z0-9][a-z0-9+.\-]{1,100}")
PROTECTED = re.compile(r"^(systemd.*|libc6|dpkg|apt|bash|coreutils|util-linux|udev|initramfs-tools.*|"
                       r"grub.*|linux-image.*|linux-base|live-boot.*|live-config.*|cfos.*|python3.*|network-manager|"
                       r"cups|sane-utils|libvirt.*|qemu.*|labwc|greetd)$")
_ENV = {**os.environ, "LC_ALL": "C", "DEBIAN_FRONTEND": "noninteractive"}
_INST = re.compile(r"^Inst (\S+)(?: \[([^\]]+)\])? \(([^ )]+)")
_REMV = re.compile(r"^(Remv|Purg) (\S+)(?: \[([^\]]+)\])?")


def _apt(args: list[str], timeout: int = 900):
    return RUN(["apt-get", *args], capture_output=True, text=True, timeout=timeout, env=_ENV, check=False)


def _audit(event: str, **fields) -> None:
    try:
        AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
        with AUDIT_LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"ts": time.time(), "event": event, "uid": os.geteuid(), **fields}, ensure_ascii=False) + "\n")
    except OSError:
        pass  # audit failure must not hide the operation result, but apply() checks writability first


def _installed_version(pkg: str) -> str | None:
    r = RUN(["dpkg-query", "-W", "-f=${Status}|${Version}", pkg], capture_output=True, text=True, check=False)
    if r.returncode != 0 or "install ok installed" not in r.stdout:
        return None
    return r.stdout.split("|", 1)[1].strip()


def _simulate(package: str) -> dict:
    r = _apt(["-s", "--no-install-recommends", "install", package], timeout=120)
    if r.returncode != 0:
        raise ValueError("apt cannot satisfy this request: " + (r.stderr.strip().splitlines() or ["unknown error"])[-1])
    installs, removals = [], []
    for line in r.stdout.splitlines():
        m = _INST.match(line)
        if m:
            installs.append({"package": m.group(1), "old_version": m.group(2), "new_version": m.group(3)})
            continue
        m = _REMV.match(line)
        if m:
            removals.append({"package": m.group(2), "version": m.group(3)})
    return {"installs": installs, "removals": removals}


def _digest(sim: dict) -> str:
    return hashlib.sha256(json.dumps(sim, sort_keys=True).encode()).hexdigest()


def _plan_path(plan_id: str) -> Path:
    if not re.fullmatch(r"[0-9a-f]{12}", plan_id or ""):
        raise ValueError("Invalid plan id")
    return STATE_DIR / "plans" / f"{plan_id}.json"


def _load(plan_id: str) -> dict:
    try:
        return json.loads(_plan_path(plan_id).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"Plan not found: {plan_id}") from exc


def _save(plan: dict) -> None:
    path = _plan_path(plan["plan_id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def _blocked(sim: dict) -> list[str]:
    reasons = [f"would remove {x['package']}" for x in sim["removals"]]
    reasons += [f"touches protected package {x['package']}" for x in sim["installs"] if PROTECTED.match(x["package"])]
    return reasons


def plan_from_device(device: str) -> list[str]:
    """Distinct repository packages suggested for a device (read-only)."""
    from .driver_manager import inspect_device
    info = inspect_device(device)
    names = {m["installed_package"] for m in info["candidate_modules"] if m.get("installed_package")}
    return sorted(n for n in names if PKG_RE.fullmatch(n))


def plan(package: str, device: str | None = None) -> dict:
    package = (package or "").strip()
    if not PKG_RE.fullmatch(package):
        raise ValueError("Invalid package name")
    if PROTECTED.match(package):
        raise ValueError(f"{package} is a protected system package and cannot be managed by CFOS")
    sim = _simulate(package)
    blocked = _blocked(sim)
    now = time.time()
    record = {
        "plan_id": uuid.uuid4().hex[:12], "package": package, "device": device,
        "created_at": now, "expires_at": now + PLAN_TTL, "status": "planned",
        "simulation": sim, "digest": _digest(sim), "blocked_reasons": blocked,
        "firmware_packages": [x["package"] for x in sim["installs"] if x["package"].startswith("firmware-")],
        "prior_versions": {x["package"]: x["old_version"] for x in sim["installs"]},
        "approved_to_apply": not blocked,
    }
    _save(record)
    _audit("plan", plan_id=record["plan_id"], package=package, device=device, blocked=blocked)
    return record


def _need_root():
    if os.geteuid() != 0:
        raise PermissionError("This operation requires root (use sudo) and --local")


def apply(plan_id: str, approve: str, offline: bool = False) -> dict:
    _need_root()
    if approve != plan_id:
        raise PermissionError("Approval refused: --approve must repeat the exact plan id")
    p = _load(plan_id)
    if p["status"] != "planned":
        raise ValueError(f"Plan is not in 'planned' state (state: {p['status']})")
    if time.time() > p["expires_at"]:
        p["status"] = "expired"; _save(p)
        raise ValueError("Plan expired; create a new plan")
    if p["blocked_reasons"]:
        raise PermissionError("Plan is blocked: " + "; ".join(p["blocked_reasons"]))
    AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    if not os.access(AUDIT_LOG.parent, os.W_OK):
        raise PermissionError("Audit log is not writable; refusing to proceed without an audit trail")
    fresh = _simulate(p["package"])
    if _digest(fresh) != p["digest"]:
        raise RuntimeError("System package state changed since the plan was made; create a new plan")
    _audit("apply_start", plan_id=plan_id, package=p["package"], offline=offline)
    args = ["install", "-y", "--no-install-recommends"] + (["--no-download"] if offline else []) + [p["package"]]
    r = _apt(args)
    ok = r.returncode == 0 and _installed_version(p["package"]) is not None
    p["status"] = "applied" if ok else "failed"
    p["applied_at"] = time.time()
    _save(p)
    _audit("apply_done", plan_id=plan_id, ok=ok, returncode=r.returncode)
    if not ok:
        raise RuntimeError("apt install failed: " + (r.stderr.strip().splitlines() or ["unknown error"])[-1]
                           + f" -- state recorded as failed; review with rollback if needed (plan {plan_id})")
    return {"plan_id": plan_id, "status": "applied", "installed_version": _installed_version(p["package"]),
            "reboot_or_module_load_may_be_required": True, "modules_loaded": False, "firmware_packages": p["firmware_packages"]}


def rollback(plan_id: str, approve: str) -> dict:
    _need_root()
    if approve != plan_id:
        raise PermissionError("Approval refused: --approve must repeat the exact plan id")
    p = _load(plan_id)
    if p["status"] not in {"applied", "failed"}:
        raise ValueError(f"Nothing to roll back (state: {p['status']})")
    new_pkgs = [x["package"] for x in p["simulation"]["installs"] if not x["old_version"]]
    old_pkgs = [(x["package"], x["old_version"]) for x in p["simulation"]["installs"] if x["old_version"]]
    _audit("rollback_start", plan_id=plan_id)
    errors = []
    if new_pkgs:
        r = _apt(["remove", "-y", *new_pkgs])
        if r.returncode != 0:
            errors.append("remove: " + (r.stderr.strip().splitlines() or ["error"])[-1])
    for name, ver in old_pkgs:
        r = _apt(["install", "-y", "--allow-downgrades", "--no-install-recommends", f"{name}={ver}"])
        if r.returncode != 0:
            errors.append(f"downgrade {name}={ver}: " + (r.stderr.strip().splitlines() or ["error"])[-1])
    p["status"] = "rollback_failed" if errors else "rolled_back"
    _save(p)
    _audit("rollback_done", plan_id=plan_id, errors=errors)
    if errors:
        raise RuntimeError("; ".join(errors))
    return {"plan_id": plan_id, "status": "rolled_back", "removed": new_pkgs, "restored": [f"{n}={v}" for n, v in old_pkgs]}
