# CFOS Core v0.6 — Driver Intelligence & Driver Manager

## Implemented
- Read-only driver inspection for USB and PCI devices.
- Kernel module candidate lookup through `modprobe --resolve-alias` using sysfs modalias values.
- Bound-driver detection from sysfs and module-loaded state from `/sys/module`.
- Best-effort module file and Debian package ownership lookup using `modinfo` and `dpkg-query`.
- Best-effort repository candidate lookup from the local APT cache using `apt-cache policy`.
- Explicit confidence/state labels: `driver_bound`, `matching_module_available`,
  `no_matching_module_found`, and `modalias_unavailable`.
- No automatic package installation, module loading, firmware download, or network access.
- New commands: `cfos drivers [--local] [--json]` and
  `cfos driver --device <USB_SYSFS_ID|PCI_BDF> [--local] [--json]`.
- The driver report is available through the local CLI and the existing CFOS Core socket.

## Usage
```bash
cfos drivers --local
cfos drivers --local --json
cfos driver --device 1-2 --local
cfos driver --device 0000:00:1f.6 --local --json
```

## Safety and interpretation
- Candidate modules are suggestions derived from the running system's module alias database;
  they are not a guarantee of full hardware support.
- Package ownership may be absent for built-in modules, custom kernels, or non-Debian layouts.
- APT candidate versions come only from the local package cache and configured sources metadata.
  No package is downloaded or installed.
- Missing driver binding can be normal for devices handled by userspace, firmware, or composite interfaces.
- Installation and firmware workflows are deliberately deferred to a later milestone with
  explicit confirmation, dependency review, and rollback planning.

## Dependencies
- `kmod` provides `modprobe` and `modinfo`; Debian base tooling provides `dpkg-query` and `apt-cache`.
- Optional tools are detected at runtime. Missing tools reduce report detail but do not break inventory.

## v0.6.1 fixes
- `cfos hardware` crashed with `KeyError: 'function'` when any non-network PCI device was present
  (summary counters indexed a USB-only field on PCI entries). Counters now use `.get()`.
- A device with no `driver` symlink was reported as bound to a driver named `driver`
  (non-strict `Path.resolve()`), hiding devices that actually need review. A shared
  `collector.bound_driver()` helper now checks for the symlink first; used by USB and PCI paths.
- Added `core/tests/test_regressions_v061.py`.
