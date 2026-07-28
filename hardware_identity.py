# -*- coding: utf-8 -*-
"""Tạo mã máy ổn định từ CPU, MAC và mainboard."""
import hashlib
import os
import re
import subprocess
import sys
import uuid

_identity_cache = None
_INVALID_VALUES = {
    "", "none", "null", "unknown", "defaultstring", "tobefilledbyo.e.m.",
    "systemserialnumber", "00000000", "ffffffff",
}


def _clean(value) -> str:
    value = re.sub(r"\s+", "", str(value or "")).upper()
    return "" if value.lower() in _INVALID_VALUES else value


def _powershell_values(command: str):
    if not sys.platform.startswith("win"):
        return []
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
            capture_output=True, text=True, timeout=8, startupinfo=startupinfo,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode != 0:
            return []
        return [v for line in result.stdout.splitlines() if (v := _clean(line))]
    except Exception:
        return []


def get_hardware_identity():
    global _identity_cache
    if _identity_cache is not None:
        return dict(_identity_cache)
    cpus = _powershell_values(
        "Get-CimInstance Win32_Processor | Select-Object -ExpandProperty ProcessorId"
    )
    boards = _powershell_values(
        "Get-CimInstance Win32_BaseBoard | Select-Object -ExpandProperty SerialNumber"
    )
    macs = _powershell_values(
        "Get-CimInstance Win32_NetworkAdapter | "
        "Where-Object {$_.PhysicalAdapter -eq $true -and $_.MACAddress} | "
        "Sort-Object MACAddress | Select-Object -ExpandProperty MACAddress"
    )
    cpu = cpus[0] if cpus else _clean(os.environ.get("PROCESSOR_IDENTIFIER"))
    mainboard = boards[0] if boards else _clean(uuid.getnode())
    mac = macs[0] if macs else f"{uuid.getnode():012X}"
    mac = re.sub(r"[^0-9A-F]", "", mac)
    _identity_cache = {
        "cpu": cpu or "CPU-UNAVAILABLE",
        "mac": mac or "MAC-UNAVAILABLE",
        "mainboard": mainboard or "BOARD-UNAVAILABLE",
    }
    return dict(_identity_cache)


def get_machine_code() -> str:
    """Mã công khai để dán vào Google Sheet, không lộ serial gốc."""
    hw = get_hardware_identity()
    raw = f"ATG|CPU={hw['cpu']}|MAC={hw['mac']}|BOARD={hw['mainboard']}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest().upper()
    return "ATG-" + "-".join(digest[i:i + 5] for i in range(0, 25, 5))


def get_machine_secret() -> bytes:
    hw = get_hardware_identity()
    raw = f"ATG-LOCAL|{hw['cpu']}|{hw['mac']}|{hw['mainboard']}"
    return hashlib.sha256(raw.encode("utf-8")).digest()
