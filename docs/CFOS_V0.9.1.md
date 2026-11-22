# CFOS Base v0.9.1 — boot-fix candidate

Date: 2026-11-22

This source update addresses the first-boot failure reported for v0.9. The earlier ISO reached tty1 on the Pentium E5700 but showed `user` and `debian`, failed automatic login, and did not start the graphical session. The attached handoff report is retained as a historical snapshot; this document records the candidate changes made afterward.

## Changes

- Use explicit `live-config.*` parameters for the `cfos` user, hostname, locale, keyboard layout, and supplementary groups. Keep live-config debug output enabled while diagnosing.
- Disable live-config autologin. greetd is ordered after `live-config.service`, owns the graphical auto-start, and has a tuigreet fallback.
- Remove the pre-created `cfos` system account from sysusers. The shared `cfos` group remains for the Core daemon socket; live-config creates the regular session account and adds it to that group.
- Explicitly disable Debian Installer in the default image.
- Generate `/var/log/cfos/boot-report-latest.txt` automatically after the CFOS Core and greetd services start.
- Update the image identity and acceptance documentation.

The live-config parameter names and the behavior of `noautologin` are documented for Debian Trixie. greetd documents `initial_session` as its one-time automatic session and `default_session` as the session used when no user session is active. live-build documents that Debian Installer is omitted by default; this candidate sets it explicitly to `none`. The choices match the tools' documented behavior, but do not by themselves prove the image boots correctly. [Debian live-config manual](https://manpages.debian.org/trixie/live-config-doc/live-config.7.en.html), [Debian greetd manual](https://manpages.debian.org/trixie/greetd/greetd.5.en.html), [Debian live-build manual](https://manpages.debian.org/trixie/live-build/lb_config.1.en.html).

## Validation still required

1. Rebuild the ISO in the Debian Trixie GitHub Actions workflow and keep the new checksum.
2. Boot that exact ISO on the Core i5-4440. Confirm hostname, account groups, greetd, report file, sound/network basics, and a clean or explained failed-unit list.
3. Boot it on the Pentium E5700 in Legacy BIOS mode and confirm the same login/session behavior with the older GPU.
4. Run the hardware acceptance checks for USB, printers, scanners, and CUPS/SANE. These are not covered by a boot test.

If the display fails, use tuigreet to sign in as `cfos` with the live password (`live`), then inspect `/var/log/cfos/boot-report-latest.txt`. Keep the report with the ISO checksum and machine model when reporting a failure.

## DLC Boot reference review

The supplied DLC Boot 2023 v4.3 ISO was reviewed as a product and workflow reference. Its boot menus group capabilities into recognizable jobs such as Windows PE, hard-disk tools, backup/restore, operating-system setup, antivirus rescue, and other tools. Its Windows utility tree also has areas for hardware, drivers, network, and printer repair.

CFOS can carry the useful organization forward in the planned Technician Center: start with a technician's task, show the relevant device and diagnostic evidence, and make recovery actions explicit. Keep read-only diagnosis separate from actions that can change disks, drivers, queues, or firmware, and provide a clear confirmation and recovery path for those changes. Keep printer/scanner and Windows-runtime workflows visible alongside general hardware repair.

Only ISO directory names and boot-menu configuration were inspected. No programs were run, and no ISO binaries or assets were copied into CFOS.
