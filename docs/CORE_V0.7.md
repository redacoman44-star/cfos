# CFOS Core v0.7 — Approval-gated driver installation

## Workflow
```sh
# 1. Plan (read-only simulation via `apt-get -s`; changes nothing)
cfos driver-plan --local --package firmware-realtek
cfos driver-plan --local --device 0000:03:00.0        # only if the device maps to exactly one package

# 2. Apply (root, local only). The technician must repeat the exact plan id.
sudo cfos driver-apply --local --plan <ID> --approve <ID> [--offline]

# 3. Roll back if needed (root, local only, same approval rule)
sudo cfos driver-rollback --local --plan <ID> --approve <ID>
```

## Safeguards
- Plans expire after 15 minutes and are re-simulated at apply time; any change in the
  simulated result (different packages/versions) aborts the apply.
- A plan that would remove any package, or touch protected system packages (systemd, libc6,
  linux-image*, grub*, python3*, cfos*, libvirt/qemu, etc.), is blocked and cannot be applied.
- Package names are validated against a strict pattern; apt is invoked without a shell.
- Apply/rollback are never exposed through the daemon socket and need root.
- Apply refuses to run if the audit log directory is not writable. Every plan/apply/rollback
  is appended as JSON lines to `/var/log/cfos/audit.log` (override: `CFOS_AUDIT_LOG`).
- State is kept in `/var/lib/cfos/plans/<id>.json` (override: `CFOS_STATE_DIR`).
- `--offline` uses `--no-download` (only already-cached .deb files).
- Kernel modules are not loaded and firmware is not downloaded outside apt; a reboot or
  manual module load may be needed afterwards.

## Rollback semantics
Newly installed packages are removed (`apt-get remove`, not purge). Upgraded packages are
downgraded to the recorded previous version, which requires that version to be available
in the APT cache or configured sources. A failed rollback is recorded as `rollback_failed`.

## Limitations (not yet done)
- Dependency/conflict review is limited to what apt's simulation reports.
- Not yet validated on a real Debian 13 host with network access; tests mock apt/dpkg.
- Orphaned dependencies from an installed package are not auto-removed on rollback.
