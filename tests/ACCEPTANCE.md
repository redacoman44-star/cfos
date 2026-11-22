# CFOS Acceptance Checks

## Static and unit checks

```sh
./scripts/check-config.sh
PYTHONPATH=core python3 -m unittest discover -s core/tests -v
python3 -m compileall -q core/cfos_core
bash -n scripts/*.sh
```

## Hardware validation (Debian 13 target required)

- Confirm `cfos devices` lists the intended printer/scanner and stable sysfs ID.
- Confirm HID, hub, storage and unknown USB classes are refused for passthrough.
- With a disposable running libvirt VM, attach a test USB printer, verify guest
  visibility, detach it, and verify host reattachment.
- Test persistent attach only on a disposable VM definition.
- Verify that a failed attach releases the CFOS reservation.
- Confirm the host keyboard, mouse, boot storage and network remain usable.

## v0.7 driver installation (Debian 13 target required)
- `cfos driver-plan --local --package <pkg>` shows installs/removals and changes nothing (`dpkg -l` unchanged).
- Apply without `--approve`, with a wrong id, or as non-root is refused.
- Apply after `apt` state changes (e.g. another install) aborts.
- Apply succeeds on a disposable machine; `/var/log/cfos/audit.log` has plan/apply_start/apply_done.
- Rollback removes the package / restores the previous version; host network and boot remain usable.

## v0.8 USB lifecycle (Debian 13 + libvirt target required)
- Reserve+attach a printer, unplug it: `usb-reconcile` shows `device_missing`; `sudo usb-recover` releases it.
- Shut down the VM without persistent attach: `owner_not_running`; with `--persistent`: `reserved_for_persistent`.
- Persistent attach, replug the printer (new bus/device number), start the VM: device still passes through.
- Attach a device manually with virsh: `usb-reconcile` lists an orphan and suggests the command.
- Simulate an attach timeout: reservation is kept unless libvirt confirms the device is not attached.

## v0.9 ISO build and boot (real hardware)
- `scripts/check-packages.sh` reports 0 missing packages on Debian 13.
- `lb build` finishes and produces an ISO; `sha256sum` recorded.
- ISO boots from USB in Legacy BIOS (and UEFI on a machine that has it) to the login screen / labwc session.
- `/proc/cmdline` includes `live-config.username=cfos`, `live-config.hostname=cfos`, and `live-config.noautologin`; boot messages are visible.
- `hostname` reports `cfos`; `id cfos` includes the `cfos` group; `getent passwd cfos` points to a normal live home and shell.
- greetd starts Labwc automatically as `cfos`; if Labwc fails, tuigreet is available and the console has no competing automatic login.
- No Debian installer entry is present in the default boot menu.
- `/var/log/cfos/boot-report-latest.txt` is readable and includes the current kernel command line, failed units, graphics, PCI/USB, and CFOS diagnostics.
- `systemctl --failed` is empty or explained; `cfos status` works via the daemon.
- `cfos hardware --local` and `cfos drivers --local` list the real PCI/USB devices; RAM use at idle is noted (`free -m`).
- Network (wired/Wi-Fi), USB printer detection (`cfos devices`), CUPS and SANE start without errors.
