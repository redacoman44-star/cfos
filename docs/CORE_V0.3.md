# CFOS Core v0.3 — Device Manager

## Implemented

1. Live USB inventory from sysfs, enriched with CFOS reservation state.
2. SQLite-backed atomic reservation and release operations. `BEGIN IMMEDIATE` serializes competing reservation attempts.
3. Owner-checked release to reduce accidental release by another runtime.
4. Optional pyudev USB add/remove event history.
5. CLI and Unix-socket API commands: `devices`, `events`, `reserve`, `release`.
6. Unit tests for reservation conflicts, ownership checks, missing devices, inventory state and event history.
7. Debian live-build staging for the Python package, CLI launcher, pyudev dependency and systemd unit.

## Safety boundaries

- Reservation is advisory CFOS coordination only; it is not hardware isolation.
- No USB driver detach, sysfs writes, permission changes, VM passthrough or runtime launch is performed.
- The daemon exposes a fixed command allowlist and accepts bounded JSON requests.
- The service remains disabled by default pending validation on real hardware.

## Manual validation on Debian 13

```sh
sudo systemctl start cfos-core.service
cfos devices
cfos events
# Use an actual sysfs_name shown by `cfos devices`:
sudo cfos reserve --device 1-2 --owner windows-vm
cfos devices
sudo cfos release --device 1-2 --owner windows-vm
```

Only reserve a device after confirming it is not needed by the host desktop, storage, input devices or another runtime.
