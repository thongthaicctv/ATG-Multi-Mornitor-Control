# -*- coding: utf-8 -*-
"""Online-first license validation with a machine-bound encrypted offline cache."""
import csv
import io
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta

from common import APP_DIR, resource_log
from hardware_identity import get_machine_code
from secure_storage import load_encrypted_json, save_encrypted_json

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

SHEET_ID = "1dsoD_Ljon4BNie2T3VCD51Vx2klJMbjqpbNHBRO8hRk"
SHEET_GID = "0"
CSV_EXPORT_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={SHEET_GID}"
PROGRAM_DATA = os.environ.get("PROGRAMDATA", r"C:\ProgramData")
CACHE_PATH = os.path.join(PROGRAM_DATA, "AnNguyen", "ATGMultiMonitorControl", "license_cache.atg")
LEGACY_CACHE_PATH = os.path.join(APP_DIR, "license_cache.atg")
DEFAULT_OFFLINE_DAYS = 0
MAX_OFFLINE_DAYS = 365
CLOCK_ROLLBACK_TOLERANCE = timedelta(minutes=5)

COLUMN_ALIASES = {
    "licensekey": "LicenseKey", "malicense": "LicenseKey",
    "tenkhachhang": "TenKhachHang", "khachhang": "TenKhachHang",
    "trangthai": "TrangThai", "status": "TrangThai",
    "ngayhethan": "NgayHetHan", "hanketthuc": "NgayHetHan", "expiry": "NgayHetHan",
    "mamay": "MaMay", "machinecode": "MaMay", "machineid": "MaMay",
    "thoigianoffline": "ThoiGianOffline", "songayoffline": "ThoiGianOffline",
    "offlinedays": "ThoiGianOffline", "ghichu": "GhiChu", "note": "GhiChu",
}


@dataclass(frozen=True)
class LicenseResult:
    valid: bool
    message: str
    source: str  # online, offline, unavailable, or local
    reason: str  # ok, missing, expired, blocked, wrong_machine, offline_expired, etc.


def _normalize_header(value: str) -> str:
    key = (value or "").strip().lower().replace(" ", "").replace("_", "")
    return COLUMN_ALIASES.get(key, value.strip())


def _fetch_license_rows():
    if not REQUESTS_AVAILABLE:
        resource_log("[LICENSE] ONLINE UNAVAILABLE")
        return None
    try:
        separator = "&" if "?" in CSV_EXPORT_URL else "?"
        response = requests.get(
            f"{CSV_EXPORT_URL}{separator}_={time.time_ns()}",
            headers={"Cache-Control": "no-cache, no-store", "Pragma": "no-cache"},
            timeout=10,
        )
        response.raise_for_status()
        rows = list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))
        if not rows:
            return []
        headers = [_normalize_header(value) for value in rows[0]]
        return [
            {header: raw[index].strip() if index < len(raw) else "" for index, header in enumerate(headers)}
            for raw in rows[1:] if any(cell.strip() for cell in raw)
        ]
    except Exception as exc:
        resource_log(f"[LICENSE] ONLINE UNAVAILABLE ({type(exc).__name__})")
        return None


def _parse_date(value: str):
    value = (value or "").strip()
    if not value:
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(value, fmt) + timedelta(days=1)
        except ValueError:
            pass
    return "invalid"


def _parse_offline_days(value: str):
    value = (value or "").strip()
    if not value:
        return DEFAULT_OFFLINE_DAYS
    try:
        days = int(float(value.replace(",", ".")))
        return max(0, min(days, MAX_OFFLINE_DAYS))
    except ValueError:
        return None


def _load_cache():
    try:
        return load_encrypted_json(CACHE_PATH, "license-cache")
    except FileNotFoundError:
        # One-time compatibility path for caches created beside older EXEs.
        try:
            cache = load_encrypted_json(LEGACY_CACHE_PATH, "license-cache")
            save_encrypted_json(CACHE_PATH, cache, "license-cache")
            resource_log("[LICENSE] Migrated legacy encrypted cache to ProgramData")
            return cache
        except FileNotFoundError:
            return None
        except Exception as exc:
            resource_log(f"[LICENSE] Legacy cache cannot be decrypted ({type(exc).__name__})")
            return {"_cache_error": True}
    except Exception as exc:
        resource_log(f"[LICENSE] Cache cannot be decrypted ({type(exc).__name__})")
        return {"_cache_error": True}


def _save_cache(key, valid, message, offline_days, customer="", license_expiry=None):
    now = datetime.now().isoformat(timespec="seconds")
    data = {
        "license_key": key,
        "machine_code": get_machine_code(),
        "valid": bool(valid),
        "customer": customer,
        "license_expiry": license_expiry.isoformat(timespec="seconds") if isinstance(license_expiry, datetime) else None,
        "offline_days": int(offline_days),
        "online_checked_at": now,
        "last_seen_at": now,
        "message": message,
    }
    try:
        save_encrypted_json(CACHE_PATH, data, "license-cache")
    except Exception as exc:
        resource_log(f"[LICENSE] Cache write failed ({type(exc).__name__})")


def _offline_failure(message, reason):
    if reason == "clock_rollback":
        resource_log("[LICENSE] CLOCK ROLLBACK DETECTED")
    elif reason in ("offline_expired", "expired"):
        resource_log("[LICENSE] OFFLINE CACHE EXPIRED")
    return LicenseResult(False, message, "offline", reason)


def _validate_offline(key: str):
    cache = _load_cache()
    if not cache:
        return _offline_failure("Không thể kết nối Google Sheet và không có cache License hợp lệ.", "cache_missing")
    if cache.get("_cache_error"):
        return _offline_failure("Cache License bị hỏng hoặc không thể giải mã.", "cache_corrupt")
    if str(cache.get("license_key", "")).casefold() != key.casefold():
        return _offline_failure("Cache License không thuộc License Key hiện tại.", "wrong_key")
    if cache.get("machine_code") != get_machine_code():
        return _offline_failure("Cache License không thuộc máy hiện tại.", "wrong_machine")
    if cache.get("valid") is not True:
        return _offline_failure(cache.get("message") or "License trong cache không hợp lệ.", "cached_invalid")
    try:
        checked = datetime.fromisoformat(cache["online_checked_at"])
        last_seen = datetime.fromisoformat(cache["last_seen_at"])
        now = datetime.now()
        offline_days = int(cache["offline_days"])
        expiry_text = cache.get("license_expiry")
        license_expiry = datetime.fromisoformat(expiry_text) if expiry_text else None
    except (KeyError, TypeError, ValueError):
        return _offline_failure("Cache License không đúng định dạng.", "cache_corrupt")
    if now + CLOCK_ROLLBACK_TOLERANCE < last_seen or now + CLOCK_ROLLBACK_TOLERANCE < checked:
        return _offline_failure("Đồng hồ hệ thống đã bị lùi; cần kết nối Internet để xác minh License.", "clock_rollback")
    offline_expiry = checked + timedelta(days=offline_days)
    effective_expiry = min(offline_expiry, license_expiry) if license_expiry else offline_expiry
    if now >= effective_expiry:
        if license_expiry and license_expiry <= offline_expiry and now >= license_expiry:
            return _offline_failure("License đã hết hạn; cần kết nối Internet để xác minh lại.", "expired")
        return _offline_failure("Cache đã hết thời gian Offline; cần kết nối Internet.", "offline_expired")
    cache["last_seen_at"] = now.isoformat(timespec="seconds")
    try:
        save_encrypted_json(CACHE_PATH, cache, "license-cache")
    except Exception:
        pass
    resource_log("[LICENSE] OFFLINE CACHE OK")
    return LicenseResult(True, "License hợp lệ — Offline cache", "offline", "ok")


def validate_license_detailed(cfg: dict) -> LicenseResult:
    key = (cfg.get("license_key") or "").strip()
    if not key:
        return LicenseResult(False, "Chưa có License Key.", "local", "missing_key")

    rows = _fetch_license_rows()
    if rows is None:
        return _validate_offline(key)

    row = next((item for item in rows if item.get("LicenseKey", "").strip().casefold() == key.casefold()), None)
    if row is None:
        message, reason = "License Key không tồn tại.", "missing"
        _save_cache(key, False, message, 0)
    else:
        customer = (row.get("TenKhachHang") or "").strip()
        expiry = _parse_date(row.get("NgayHetHan", ""))
        offline_days = _parse_offline_days(row.get("ThoiGianOffline", ""))
        registered_machine = (row.get("MaMay") or "").strip().upper()
        status = (row.get("TrangThai") or "").strip().casefold()
        if not registered_machine or registered_machine != get_machine_code().upper():
            message, reason = "Sai mã máy; License không thuộc máy hiện tại.", "wrong_machine"
        elif status in ("blocked", "khoa", "khóa", "disabled", "inactive"):
            message, reason = "License bị khóa.", "blocked"
        elif expiry == "invalid":
            message, reason = "Ngày hết hạn trên Google Sheet không đúng định dạng.", "invalid_expiry"
        elif expiry is not None and datetime.now() >= expiry:
            message, reason = "License hết hạn.", "expired"
        elif offline_days is None:
            message, reason = "Cột ThoiGianOffline phải là số ngày nguyên.", "invalid_offline_days"
        else:
            message = "License hợp lệ — Online" + (f" — {customer}" if customer else "")
            _save_cache(key, True, message, offline_days, customer, expiry)
            resource_log("[LICENSE] ONLINE OK")
            return LicenseResult(True, message, "online", "ok")
        _save_cache(key, False, message, 0, customer, expiry if isinstance(expiry, datetime) else None)

    resource_log("[LICENSE] ONLINE INVALID")
    return LicenseResult(False, message, "online", reason)


def validate_license(cfg: dict):
    result = validate_license_detailed(cfg)
    return result.valid, result.message
