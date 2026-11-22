# Build and validation

## Supported build target

Debian 13 (Trixie), amd64. Prefer a clean VM or dedicated build host. Building on another distribution is not a supported baseline.

## Host preparation

```bash
sudo apt update
sudo apt install --yes live-build debootstrap squashfs-tools xorriso isolinux syslinux-common
```

## Static checks

```bash
./scripts/check-config.sh
```

## ISO build

```bash
sudo ./scripts/build-iso.sh
```

## Test the ISO

Use a disposable QEMU/KVM VM first. Verify UEFI boot, live session, network, USB enumeration, CUPS service, SANE device discovery, and shutdown. Then test on physical hardware. Do not treat a successful VM boot as proof of printer/scanner/firmware compatibility.

## v0.9.1 candidate — boot configuration and diagnosis

The previous v0.9 image was reported to build and reach tty1 on a Pentium E5700, but it did not reach the graphical session and showed the default `user`/`debian` identity. The v0.9.1 source candidate changes live-config identity/group parameters, removes the conflicting `cfos` service user, disables live-config autologin so greetd owns the session, and adds a boot-time diagnostic report. These changes still need a fresh ISO build and hardware validation.

Expected behavior:

1. The kernel command line names the live account and host as `cfos` and keeps boot messages visible.
2. greetd starts Labwc as `cfos`; if Labwc exits, tuigreet remains available for recovery.
3. The live account belongs to the `cfos` group so it can access the CFOS Core socket.
4. A report is saved at `/var/log/cfos/boot-report-latest.txt` after services start.
5. The default boot menu does not offer the Debian installer.

Test the same new ISO on the Core i5-4440 first, then on the Pentium E5700. Check `/proc/cmdline`, `hostname`, `id cfos`, `systemctl --failed`, and the report file. If the desktop does not appear, sign in at tuigreet with the live account password (`live`) and inspect the report. Do not treat a successful QEMU boot as proof of real printer/scanner compatibility.

## v0.9 — building and testing with limited hardware (e.g. Pentium E5700, 4 GB RAM)

The Pentium E5700 (Core 2 generation) normally has **no VT-x**, so KVM is unavailable: QEMU runs in
slow software emulation. Recommended path:

1. **Build in the cloud (GitHub Actions)** — no load on the old PC. Put the contents of this project
   at the root of a GitHub repository, open *Actions → Build CFOS ISO → Run workflow*, then download the
   `cfos-iso` artifact (ISO + `SHA256SUMS`). The previous v0.9 build was reported successful; rebuild
   this v0.9.1 candidate before testing it.
2. **Or build locally** on Debian 13 (installed or live-USB with enough disk): needs roughly 15 GB free
   disk and 2 GB+ RAM; expect 1–2+ hours on this CPU. Run `./scripts/check-packages.sh` first.
3. **Test on the real machine from USB**, not in QEMU. Write the ISO with `dd` (Linux) or Rufus (DD mode)
   / balenaEtcher (Windows) and boot in Legacy/CSM mode (this class of board is usually BIOS-only).
4. In the live session run `sudo cfos-boot-report` and keep the report file for debugging.

`scripts/test-iso-qemu.sh <iso>` is an optional smoke test (software emulation, slow).

### Remaining validation
- Build and boot this exact source revision; the previous v0.9 ISO result does not validate it.
- Verify the user, hostname, greetd session, and automatic report on both target machines.
- Old GPUs: `WLR_RENDERER_ALLOW_SOFTWARE=1` is set as a fallback; its effect on the exact hardware is untested.
- Windows (KVM) and Waydroid runtimes need hardware the Pentium machine lacks; test them on a newer computer.
