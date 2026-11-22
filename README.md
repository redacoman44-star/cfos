# CFOS Base v0.9.1 candidate

CFOS (Computer Field Operating System) is a Debian 13 live environment for computer and printer technicians. This source package advances the existing v0.9 base with a safer boot and session configuration. It is a development candidate, not a hardware-certified release.

## Scope

- Debian 13 (Trixie), amd64, Live ISO
- Linux host architecture
- Lightweight Wayland session (Labwc) as a temporary development desktop
- Hardware/network/storage diagnostics
- CUPS printing and SANE scanning foundations
- Directory/API placeholders for future CFOS Core services

No ISO is included. Build it on a Debian 13 amd64 machine or compatible Debian environment with working network access. The v0.9.1 changes have not yet been rebuilt or verified on hardware.

## Build prerequisites

```bash
sudo apt update
sudo apt install --yes live-build debootstrap squashfs-tools xorriso isolinux syslinux-common
```

## Build

```bash
chmod +x auto/config scripts/*.sh
sudo ./scripts/build-iso.sh
```

The ISO output is produced in the project root by live-build. The build script refuses to run as a non-root user because live-build requires system-level operations.

## Clean

```bash
sudo ./scripts/clean-build.sh
```

## Important design notes

1. Linux is the host kernel. Wine and Waydroid are planned runtime integrations, not separate kernels.
2. Windows 10 native kernel compatibility requires a KVM/QEMU virtual machine; Wine is an API compatibility layer and cannot run Windows kernel drivers.
3. Android 13 is the planned default Waydroid image. Multi-version image switching is a later milestone and must validate matching system/vendor images and container state.
4. Printer reset utilities and vendor service tools may require a real Windows VM with USB passthrough. Wine compatibility must be tested per application/device.
5. The included Labwc session is a lightweight temporary desktop foundation. It is not the final CFOS visual identity. The custom Qt/QML shell is a later milestone and must preserve the approved CFOS glass styling and colors.

## Repository layout

- `auto/config`: reproducible live-build configuration entry point
- `config/package-lists`: package selection
- `config/includes.chroot`: files copied into the live filesystem
- `config/hooks/normal`: chroot customization hooks
- `core/`: planned CFOS service boundaries and API contracts
- `scripts/`: build, clean and validation scripts
- `docs/`: architecture and build notes
- `tests/`: static configuration checks

## CFOS Core v0.2 (implemented)

The project includes an executable diagnostics core. See `core/README.md`.

Available commands include `cfos status`, `cfos resources`, `cfos devices`, and `cfos sessions`. Use `--local` for direct diagnostics without the daemon. In this candidate, the core service is enabled for image validation.

## CFOS Core v0.3 — USB Device Manager

The current source tree advances Core to v0.3. It adds live USB inventory with reservation state, atomic SQLite-backed device reservations, owner-checked release, and optional udev add/remove event history. See `docs/CORE_V0.3.md` and `core/README.md` for commands and safety boundaries.

The CLI launcher, Python modules, systemd unit and sysusers definition are staged under `config/includes.chroot`. Reservations coordinate CFOS clients only; they do not detach drivers or pass devices through to virtual machines.

## CFOS Core v0.4 (implemented)

Adds guarded, explicit USB passthrough to running libvirt/QEMU domains. The
operation is local-only (`sudo cfos passthrough --local ...`) and is not exposed
through the privileged daemon socket. Printer/imaging interfaces are allowed by
default; HID, hubs, storage, unknown and mixed-class devices are blocked.
Vendor-specific interfaces require an explicit opt-in. See `docs/CORE_V0.4.md`.
Virtualization packages remain optional and are not installed in the lightweight
base image by default.

## CFOS Core v0.5 (implemented)

Read-only hardware intelligence is available through `cfos hardware --local` and `cfos profile --device <USB_SYSFS_ID> --local`. It classifies USB interfaces, inventories PCI devices, reports bound drivers, and uses a confidence-labelled local vendor catalog. It does not install drivers or modify the host. See `docs/CORE_V0.5.md`.


## CFOS Core v0.6 (implemented)

Read-only driver intelligence is available through `cfos drivers --local` and
`cfos driver --device <USB_SYSFS_ID|PCI_BDF> --local`. It resolves kernel module
aliases where possible and reports bound drivers, module candidates, package ownership
and local APT candidate versions. It never installs packages, loads modules or downloads
firmware. See `docs/CORE_V0.6.md` and `docs/PROJECT_STATUS_AND_REMAINING_PLAN.md`.

## CFOS Core v0.7 (implemented)
Approval-gated driver package installation: `cfos driver-plan`, `driver-apply`, `driver-rollback` (see `docs/CORE_V0.7.md`).

## CFOS Core v0.8 (implemented)
USB lifecycle: `cfos usb-reconcile`, `usb-recover`, safer attach/persistent passthrough (see `docs/CORE_V0.8.md`).

## v0.9 build and boot validation
Cloud build workflow (`.github/workflows/build-iso.yml`), `scripts/check-packages.sh`, `cfos-boot-report`; see `docs/BUILD.md`.

## v0.9.1 boot-fix candidate
The live user is created as `cfos` without a conflicting pre-created service account. greetd waits for live-config to finish, starts Labwc for that user, and keeps tuigreet as the fallback. Live-config's own automatic logins are disabled to avoid competing with greetd; boot messages remain visible for diagnosis. A boot report is saved to `/var/log/cfos/boot-report-latest.txt`. Debian Installer is explicitly disabled. See `docs/CFOS_V0.9.1.md` for the change record and hardware acceptance steps.
