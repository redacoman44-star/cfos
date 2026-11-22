# CFOS — Comprehensive Implementation Status and Remaining Roadmap

**Baseline:** Debian 13 (Trixie), amd64, Linux host, lightweight services-on-demand.
**Current source milestone:** CFOS Base v0.9.1 boot-fix candidate / CFOS Core 0.8.0.
**Document type:** engineering status report. This report distinguishes source implementation
and automated tests from ISO builds and physical-hardware validation.

## 1. Project direction and fixed decisions

- Debian 13 Stable (Trixie), 64-bit, remains the host base.
- Linux is the host kernel. Wine/Bottles provide application compatibility, not a Windows kernel.
- KVM/QEMU is optional for full Windows environments and kernel-driver-dependent maintenance tools.
- Waydroid is the Android runtime; Android 13 is the default target, with multi-version switching planned.
- CFOS Shell is planned in Qt 6/QML. Preserve the approved glass visual identity and colors; do not substitute a new visual theme.
- Keep resource use low: start heavyweight runtimes only on demand; do not auto-start Android or Windows.
- USB device ownership must be coordinated to avoid simultaneous use by host and guest environments.
- Printing/scanning foundations: CUPS, Gutenprint, HPLIP/OpenPrinting path, SANE, sane-airscan, ipp-usb.
- Network diagnostics: NetworkManager, iproute2, ethtool, iw, tcpdump, Wireshark, nmap, iperf3 (package selection may be staged by milestone).
- Build target: Debian Live-Build ISO, with boot and install validation still outstanding.

## 2. Implemented source milestones

### Base v0.1 — project scaffold
- Live-Build configuration, package list, hooks, scripts, lightweight Labwc development session.
- Project documentation, architecture outline, acceptance checklist.
- Not a finished installable OS or final graphical shell.

### Core v0.2 — diagnostics core
- Python diagnostics modules, Unix-socket daemon, CLI, systemd unit and sysusers definition.
- Status, resource, device, session and event inspection.
- Core daemon is staged and enabled in the v0.9.1 candidate image for validation.

### Core v0.3 — USB Device Manager
- USB sysfs inventory, SQLite reservations, owner-checked release.
- Optional udev add/remove event recording.
- Reservations are CFOS coordination records, not kernel-level device isolation.

### Core v0.4 — QEMU/libvirt USB integration
- Explicit local privileged attach/detach operations using virsh/libvirt hostdev.
- Conservative interface-class allowlist; HID, storage, hubs and unknown/mixed interfaces blocked.
- Vendor-specific interfaces require explicit opt-in.
- KVM/libvirt remains optional and is not installed by default.
- Actual USB passthrough to physical printer/scanner hardware remains unverified.

### Core v0.5 — Hardware Intelligence
- USB interface classification and PCI inventory from sysfs.
- Local JSON vendor catalog with confidence labels.
- Bound-driver visibility and basic CUPS/SANE availability hints.
- No driver installation or firmware changes.

### Core v0.6 — Driver Intelligence
- Read-only modalias-to-kernel-module candidate lookup.
- Bound driver, module loaded state, module file, Debian package owner and local APT candidate where available.
- CLI and daemon commands for whole-system driver report and per-device inspection.
- No network access, package install, module load, or firmware operation.

### Core v0.7 — Driver Operations
- Explicit package plan, approval, apply and rollback flow. Package changes are simulated again immediately before apply and recorded in the audit log.

### Core v0.8 — USB lifecycle
- USB reconciliation/recovery and stable vendor/product identity for persistent passthrough. Hardware behavior remains unverified.

### Base v0.9 — ISO build
- Cloud live-build workflow and diagnostic report were added. The handoff report says the v0.9 image built and reached tty1 on the Pentium E5700, but automatic login failed and the graphical session did not appear.

### Base v0.9.1 — boot-fix candidate
- Resolves the live-user/system-user name collision, gives the live user CFOS socket-group access, orders greetd after live-config, hands automatic session startup to greetd, disables Debian Installer, and saves an automatic boot report.
- This candidate has not been built or booted yet.

## 3. Validation status

- The handoff report describes 57 passing mock-based unit tests and a successful v0.9 cloud ISO build. Those results apply to the earlier archive, not automatically to the v0.9.1 changes.
- The earlier ISO reportedly reached tty1 on a Pentium E5700, but the graphical session and login were broken. The Core i5-4440 test remains open.
- This v0.9.1 source candidate has not been rebuilt, tested, or verified on hardware.
- No statement here certifies physical USB, printer, scanner, libvirt, or driver-install behavior.

## 4. Remaining roadmap

| Priority | Milestone | Remaining work | Acceptance evidence |
|---|---|---|---|
| P0 | v0.9.1 Boot validation | Rebuild, verify live identity/session, BIOS/UEFI paths, boot report | New ISO hash, build log, both target machines |
| P1 | v1.0 CFOS Shell | Qt6/QML shell, approved glass style and colors, technician dashboard | Screenshot review and input/accessibility tests |
| P1 | v1.1 Technician Center | Hardware reports, printer/scanner/network diagnostics, logs and export | End-to-end technician workflows |
| P1 | v1.2 Printer & scanner workflows | CUPS/SANE discovery, model-specific support, queue/scan tests | Physical printer and scanner matrix |
| P1 | v1.3 Windows runtime | Optional KVM templates, VM lifecycle, snapshots, USB handoff integration | Windows guest and maintenance-tool tests |
| P1 | v1.4 Android runtime | Waydroid Android 13 baseline, image validation, start/stop and resource limits | Android boot and app tests |
| P2 | v1.5 Multi-version Android | Version catalog, compatible system/vendor pairs, safe switching and rollback | Switch tests across supported images |
| P2 | v1.6 Resource Manager | cgroups v2 policies, zram tuning, runtime budgets and idle shutdown | RAM/CPU benchmarks on low-end hardware |
| P2 | v1.7 Security & updates | Polkit authorization, signed update metadata, least privilege, audit logs | Threat review and update verification |
| P2 | v1.8 Hardware compatibility | Broader USB/PCI ID database, firmware mapping and vendor utility matrix | Tested device compatibility database |
| P2 | v1.9 Release engineering | Installer polish, recovery, documentation, release signing and support policy | Release candidate qualification |

## 5. Immediate next actions

1. Build this exact candidate on Debian 13 and record the ISO checksum and build log.
2. Verify account creation, greetd startup, and the automatic report on the Core i5-4440 and Pentium E5700.
3. Run physical USB, printer, scanner, CUPS/SANE, UEFI, and BIOS acceptance checks.
4. Design the Technician Center around task-focused workflows, using the DLC Boot review only as a high-level organization reference.
5. Keep Windows and Android runtimes disabled until explicitly launched and hardware requirements are met.

## 6. Known limitations and risks

- Hardware catalogs are intentionally small; vendor names do not imply exact model support.
- Kernel module aliases do not prove firmware availability or full device functionality.
- APT package candidates are only as fresh as local package metadata.
- USB composite devices may need interface-level passthrough rather than whole-device passthrough.
- A device cannot always be safely detached from a host kernel driver automatically.
- Waydroid images must use compatible system/vendor combinations; arbitrary Android releases cannot be mixed.
- Windows 10 is out of general support; guest OS choice and security posture must be considered.
- The final CFOS visual design is not implemented in the current Labwc scaffold.

## 7. Release statement

CFOS v0.9.1 is a development source candidate, not a certified operating-system release.
ISO creation, boot validation, installation, real-device tests, visual-shell implementation,
and security qualification remain open.
