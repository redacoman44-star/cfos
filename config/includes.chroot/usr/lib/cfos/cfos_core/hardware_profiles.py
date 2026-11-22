"""Read-only hardware profiling using sysfs and an updateable local catalog."""
from __future__ import annotations
import json
import shutil
from pathlib import Path
from .collector import _read, usb_devices, bound_driver

PROJECT_CATALOG = Path(__file__).resolve().parents[2] / "config/includes.chroot/usr/share/cfos/hardware-catalog.json"
SYSTEM_CATALOG = Path("/usr/share/cfos/hardware-catalog.json")

def _catalog() -> dict:
    for path in (SYSTEM_CATALOG, PROJECT_CATALOG):
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
    return {"usb_vendors": {}, "usb_products": {}, "pci_vendors": {}}

def _interface_classes(sysfs_name: str) -> list[str]:
    root = Path("/sys/bus/usb/devices") / sysfs_name
    result = set()
    try:
        for interface in root.glob(sysfs_name + ":*"):
            code = _read(str(interface / "bInterfaceClass")).lower()
            if code:
                result.add(code.zfill(2))
    except OSError:
        pass
    return sorted(result)

def _service_status(function: str) -> dict:
    result = {}
    if function in {"printer", "multifunction_print_scan"}:
        result["cups_available"] = bool(shutil.which("lpstat"))
    if function in {"imaging_or_scanner", "multifunction_print_scan"}:
        result["sane_available"] = bool(shutil.which("scanimage"))
    return result

def _usb_profile(device: dict, catalog: dict) -> dict:
    vid = str(device.get("vendor_id", "")).lower().zfill(4)
    pid = str(device.get("product_id", "")).lower().zfill(4)
    vendor = catalog.get("usb_vendors", {}).get(vid)
    product = catalog.get("usb_products", {}).get(f"{vid}:{pid}")
    classes = _interface_classes(device.get("sysfs_name", ""))
    if "07" in classes and "06" in classes: function = "multifunction_print_scan"
    elif "07" in classes: function = "printer"
    elif "06" in classes: function = "imaging_or_scanner"
    elif "02" in classes or "0a" in classes: function = "network_adapter"
    elif "08" in classes: function = "storage"
    elif "03" in classes: function = "human_interface"
    elif "09" in classes: function = "usb_hub"
    elif "ff" in classes: function = "vendor_specific"
    else: function = "unknown"
    driver = bound_driver(Path("/sys/bus/usb/devices") / device.get("sysfs_name", ""))
    exact = bool(product)
    return {
        "device_id":device.get("sysfs_name"),"bus":"USB","vendor_id":vid,"product_id":pid,
        "vendor_name":(product or {}).get("vendor") or (vendor or {}).get("name"),
        "model_name":(product or {}).get("name") or device.get("product") or None,
        "function":function,"interface_classes":classes,"kernel_driver":driver,
        "identification_confidence":"exact_catalog_match" if exact else ("vendor_match" if vendor else "class_only"),
        "catalog_note":(product or vendor or {}).get("note"),"services":_service_status(function),
        "needs_driver_review":function in {"printer","imaging_or_scanner","network_adapter"} and not driver
    }

def pci_devices() -> list[dict]:
    root=Path("/sys/bus/pci/devices"); items=[]
    try: entries=sorted(root.iterdir(),key=lambda p:p.name)
    except OSError: return items
    catalog=_catalog()
    for entry in entries:
        vendor=_read(str(entry/"vendor")).removeprefix("0x").lower()
        device=_read(str(entry/"device")).removeprefix("0x").lower()
        class_code=_read(str(entry/"class")).removeprefix("0x").lower()
        if not vendor or not device: continue
        info=catalog.get("pci_vendors",{}).get(vendor,{})
        driver=bound_driver(entry)
        category={"02":"network","03":"display","01":"storage","0c":"serial_bus"}.get(class_code[:2],"other")
        items.append({"device_id":entry.name,"bus":"PCI","vendor_id":vendor,"product_id":device,
          "class_code":class_code,"vendor_name":info.get("name"),"category":category,"kernel_driver":driver,
          "modalias":_read(str(entry/"modalias")) or None,
          "needs_driver_review":category in {"network","display","storage"} and not driver,
          "identification_confidence":"vendor_match" if info else "numeric_id_only"})
    return items

def hardware_inventory() -> dict:
    catalog=_catalog(); usb=[_usb_profile(d,catalog) for d in usb_devices()]; pci=pci_devices()
    return {"catalog_schema_version":catalog.get("schema_version",1),"usb":usb,"pci":pci,
      "summary":{"usb_count":len(usb),"pci_count":len(pci),
        "printers_or_multifunction":sum(x.get("function") in {"printer","multifunction_print_scan"} for x in usb),
        "scanner_candidates":sum(x.get("function") in {"imaging_or_scanner","multifunction_print_scan"} for x in usb),
        "network_adapters":sum(x.get("category")=="network" or x.get("function")=="network_adapter" for x in pci+usb),
        "driver_review_candidates":sum(bool(x["needs_driver_review"]) for x in usb+pci)}}

def profile_usb(device_id: str) -> dict:
    for item in hardware_inventory()["usb"]:
        if item.get("device_id")==device_id: return item
    raise ValueError(f"USB device not currently present: {device_id}")
