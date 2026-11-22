# CFOS Core v0.5 — Device Intelligence & Hardware Profiles

## Implemented
- Read-only USB interface classification: printer (07), imaging/scanner (06), network (02/0a), storage (08), HID (03), hub (09), vendor-specific (ff), and unknown.
- PCI inventory from sysfs, including class code, bound kernel driver and modalias.
- Local JSON vendor catalog with confidence labels. Vendor-only matches are not presented as exact model identification.
- CUPS/SANE command availability hints for relevant USB classes.
- Driver-review candidates when a relevant device has no bound kernel driver.

## Commands
```bash
cfos hardware --local
cfos hardware --local --json
cfos profile --device 1-2 --local
cfos profile --device 1-2 --local --json
```

## Accuracy and safety
The catalog is intentionally small and updateable. A vendor match does not prove a model or driver. USB class descriptors and PCI modalias/driver links are collected read-only. The tool does not install drivers, change kernel modules, modify CUPS/SANE, or download firmware. Devices with composite interfaces can be reported as multifunction or unknown depending on descriptors. Real hardware verification is still required.
