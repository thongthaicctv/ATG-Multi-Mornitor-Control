# -*- coding: utf-8 -*-
"""Kiểm tra license theo LicenseKey + mã máy từ Google Sheet."""
import csv
import io
import os
import time
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
CSV_EXPORT_URL = (
    f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={SHEET_GID}"
)
CACHE_PATH = os.path.join(APP_DIR, "license_cache.atg")
DEFAULT_OFFLINE_DAYS = 0
MAX_OFFLINE_DAYS = 365

COLUMN_ALIASES = {
    "licensekey": "LicenseKey", "malicense": "LicenseKey",
    "tenkhachhang": "TenKhachHang", "khachhang": "TenKhachHang",
    "trangthai": "TrangThai", "status": "TrangThai",
    "ngayhethan": "NgayHetHan", "hanketthuc": "NgayHetHan", "expiry": "NgayHetHan",
    "mamay": "MaMay", "machinecode": "MaMay", "machineid": "MaMay",
    "thoigianoffline": "ThoiGianOffline", "songayoffline": "ThoiGianOffline",
    "offlinedays": "ThoiGianOffline",
    "ghichu": "GhiChu", "note": "GhiChu",
}


def _normalize_header(value: str) -> str:
    key = (value or "").strip().lower().replace(" ", "").replace("_", "")
    return COLUMN_ALIASES.get(key, value.strip())


def _fetch_license_rows():
    if not REQUESTS_AVAILABLE:
        resource_log("[LICENSE] Chua cai requests, khong the kiem tra online.")
        return None
    try:
        # Thêm cache-buster để thay đổi trạng thái/ngày hết hạn trên Sheet có hiệu lực ngay.
        separator = "&" if "?" in CSV_EXPORT_URL else "?"
        url = f"{CSV_EXPORT_URL}{separator}_={time.time_ns()}"
        response = requests.get(
            url,
            headers={"Cache-Control": "no-cache, no-store", "Pragma": "no-cache"},
            timeout=10,
        )
        response.raise_for_status()
        rows = list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))
        if not rows:
            return []
        headers = [_normalize_header(value) for value in rows[0]]
        data = []
        for raw in rows[1:]:
            if not any(cell.strip() for cell in raw):
                continue
            data.append({
                header: raw[index].strip() if index < len(raw) else ""
                for index, header in enumerate(headers)
            })
        return data
    except Exception as exc:
        resource_log(f"[LICENSE] Loi tai Google Sheet: {exc}")
        return None


def _parse_date(value: str):
    value = (value or "").strip()
    if not value:
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            # Cho phép sử dụng hết ngày ghi trên Sheet.
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
        return None
    except Exception as exc:
        resource_log(f"[LICENSE] Cache khong doc duoc/da bi sua: {exc}")
        return None


def _save_cache(key: str, valid: bool, message: str, offline_days: int):
    now = datetime.now().isoformat(timespec="seconds")
    data = {
        "license_key": key,
        "machine_code": get_machine_code(),
        "valid": bool(valid),
        "message": message,
        "offline_days": int(offline_days),
        "online_checked_at": now,
        "last_seen_at": now,
    }
    try:
        save_encrypted_json(CACHE_PATH, data, "license-cache")
    except Exception as exc:
        resource_log(f"[LICENSE] Khong luu duoc cache: {exc}")


def _validate_offline(key: str):
    cache = _load_cache()
    if not cache:
        return False, "Không kết nối được Google Sheet và chưa có cache license hợp lệ."
    if cache.get("license_key", "").casefold() != key.casefold():
        return False, "Cache license không thuộc License Key hiện tại."
    if cache.get("machine_code") != get_machine_code():
        return False, "Cache license không thuộc máy hiện tại."
    if not cache.get("valid"):
        return False, cache.get("message", "License trong cache không hợp lệ.")
    try:
        checked = datetime.fromisoformat(cache["online_checked_at"])
        last_seen = datetime.fromisoformat(cache["last_seen_at"])
        now = datetime.now()
        offline_days = int(cache.get("offline_days", 0))
    except (KeyError, TypeError, ValueError):
        return False, "Cache license không đúng định dạng."
    if now + timedelta(minutes=5) < last_seen:
        return False, "Đồng hồ hệ thống đã bị lùi; cần kết nối mạng để xác minh license."
    if now - checked > timedelta(days=offline_days):
        return False, f"Đã vượt quá thời gian chạy offline {offline_days} ngày."
    cache["last_seen_at"] = now.isoformat(timespec="seconds")
    try:
        save_encrypted_json(CACHE_PATH, cache, "license-cache")
    except Exception:
        pass
    remaining = max(0, offline_days - (now - checked).days)
    return True, f"{cache['message']} (offline, còn khoảng {remaining} ngày)"


def validate_license(cfg: dict):
    key = (cfg.get("license_key") or "").strip()
    if not key:
        return False, "Chưa cấu hình License Key."
    rows = _fetch_license_rows()
    if rows is None:
        return _validate_offline(key)

    row = next(
        (item for item in rows if item.get("LicenseKey", "").strip().casefold() == key.casefold()),
        None,
    )
    if row is None:
        message = f"License Key '{key}' không tồn tại."
        _save_cache(key, False, message, 0)
        return False, message

    machine_code = get_machine_code()
    registered_machine = (row.get("MaMay") or "").strip().upper()
    if not registered_machine:
        message = "License chưa được gắn Mã máy trên Google Sheet."
        _save_cache(key, False, message, 0)
        return False, message
    if registered_machine != machine_code.upper():
        message = "License đã được gắn cho máy khác hoặc Mã máy không khớp."
        _save_cache(key, False, message, 0)
        return False, message

    status = (row.get("TrangThai") or "").strip().casefold()
    if status in ("blocked", "khoa", "khóa", "disabled", "inactive"):
        message = f"License Key '{key}' đã bị khóa."
        _save_cache(key, False, message, 0)
        return False, message

    expiry = _parse_date(row.get("NgayHetHan", ""))
    if expiry == "invalid":
        message = "Ngày hết hạn trên Google Sheet không đúng định dạng."
        _save_cache(key, False, message, 0)
        return False, message
    if expiry is not None and datetime.now() >= expiry:
        message = f"License Key '{key}' đã hết hạn."
        _save_cache(key, False, message, 0)
        return False, message

    offline_days = _parse_offline_days(row.get("ThoiGianOffline", ""))
    if offline_days is None:
        message = "Cột ThoiGianOffline phải là số ngày nguyên."
        _save_cache(key, False, message, 0)
        return False, message

    customer = (row.get("TenKhachHang") or "").strip()
    message = "License hợp lệ" + (f" — {customer}" if customer else "")
    _save_cache(key, True, message, offline_days)
    return True, f"{message} (offline tối đa {offline_days} ngày)"
