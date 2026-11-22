# CFOS Base architecture decisions

- Host kernel: Debian Linux kernel.
- Init/service manager: systemd.
- Live image: Debian Live-Build.
- Temporary graphical foundation: Wayland + Labwc + Waybar.
- Future branded desktop: Qt 6 / QML CFOS Shell.
- Windows application compatibility: Wine/Bottles; KVM/QEMU for genuine Windows kernel-driver requirements.
- Android: Waydroid, Android 13 default image; multi-version manager is a later milestone.
- Hardware: udev, libusb, CUPS, SANE, NetworkManager.

The first milestone is intentionally conservative: establish a reproducible bootable base before adding complex runtimes.
