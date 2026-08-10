# -*- coding: utf-8 -*-
"""Các hàm dùng chung cho ATG-Multi-Mornitor-Control."""
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import re
import sys

from secure_storage import load_encrypted_json, save_encrypted_json

APP_NAME = "ATG-Multi-Mornitor-Control"
APP_VERSION = "1.2.4"
APP_DISPLAY_VERSION = f"Version {APP_VERSION}"


def _detect_app_dir():
    """
    Xác định thư mục gốc của ứng dụng.
    - Khi chạy bằng Python thường (.py/.pyw): là thư mục chứa file này.
    - Khi đã đóng gói bằng PyInstaller (--onefile): __file__ sẽ trỏ vào thư mục
      tạm _MEIPASS (giải nén mỗi lần chạy rồi xoá đi), KHÔNG dùng được để lưu
      config.atg / log.txt / playlist.m3u lâu dài. Phải dùng thư mục chứa
      file .exe thực tế (sys.executable) thay thế.
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


APP_DIR = _detect_app_dir()
# Tài nguyên đóng gói nằm trong _MEIPASS; dữ liệu người dùng vẫn nằm cạnh file EXE.
RESOURCE_DIR = getattr(sys, "_MEIPASS", APP_DIR)
CONFIG_PATH = os.path.join(APP_DIR, "config.atg")
LEGACY_CONFIG_PATH = os.path.join(APP_DIR, "config.json")
PLAYLIST_PATH = os.path.join(APP_DIR, "playlist.m3u")

VIDEO_EXT = {".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm", ".mpg", ".mpeg", ".m4v", ".ts", ".mts", ".m2ts", ".3gp"}
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp", ".tif", ".tiff"}
PDF_EXT = {".pdf"}
OFFICE_EXT = {".doc", ".docx", ".rtf", ".odt", ".xls", ".xlsx", ".xlsm", ".ods", ".ppt", ".pptx", ".pptm", ".odp"}
DOCUMENT_EXT = PDF_EXT | OFFICE_EXT
MEDIA_EXT = VIDEO_EXT | IMAGE_EXT


DEFAULT_CONFIG = {
    "vlc_path": r"C:\Program Files\VideoLAN\VLC\vlc.exe",
    "media_folder": r"D:\ATG_Soft\Source",
    "source_folder": r"D:\ATG_Soft\Source",
    "play_folder": r"D:\ATG_Soft\Play",
    "libreoffice_path": "",
    "libreoffice_timeout_seconds": 180,
    "pdf_dpi": 150,
    "image_display_mode": "fit_background",
    "fit_background_style": "auto",
    "photo_background_style": "blur",
    "document_background_style": "solid",
    "document_background_color": "#FFFFFF",
    "background_blur_radius": 28,
    "background_brightness": 0.60,
    "background_saturation": 0.75,
    "foreground_max_width_percent": 1.0,
    "foreground_max_height_percent": 1.0,
    "trim_true_black_border": True,
    "black_border_threshold": 10,
    "black_border_required_ratio": 0.995,
    "black_border_max_percent": 0.08,
    "crop_target_mode": "selected_monitor",
    "crop_target_width": 1920,
    "crop_target_height": 1080,
    "normalize_image_orientation": True,
    "processed_image_format": "png",
    "jpeg_output_quality": 95,
    "recursive_scan": True,
    "remove_deleted_from_play": True,
    "sync_before_play": True,
    "sync_on_startup": True,
    "sync_debounce_seconds": 3,
    "startup_delay_seconds": 10,
    "image_duration": 10,
    "repeat_all": True,
    "fullscreen": True,
    "http_port": 8080,
    "http_password": "signage123",
    "watch_interval_seconds": 5,
    "run_on_startup": False,
    "shutdown_enabled": False,
    "shutdown_time": "22:00",
    "restart_enabled": False,
    "restart_time": "06:00",
    "license_key": "",
}


def load_config():
    if not os.path.exists(CONFIG_PATH):
        if os.path.exists(LEGACY_CONFIG_PATH):
            # Nâng cấp một lần từ JSON bản rõ; sau đó không giữ lại dữ liệu nhạy cảm.
            with open(LEGACY_CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            save_config(cfg)
            try:
                os.remove(LEGACY_CONFIG_PATH)
            except OSError:
                pass
        else:
            save_config(DEFAULT_CONFIG.copy())
    try:
        cfg = load_encrypted_json(CONFIG_PATH, "config")
    except Exception as exc:
        raise RuntimeError(
            "Không thể đọc config.atg. File đã bị chỉnh sửa hoặc được copy từ máy khác."
        ) from exc

    # Chuẩn hoá lại đường dẫn (fix các cấu hình cũ lỡ lưu dấu "/" thay vì "\" trên Windows,
    # khiến VLC không tìm thấy file media hoặc chính vlc.exe)
    original = dict(cfg)
    merged = DEFAULT_CONFIG.copy()
    merged.update(cfg)
    cfg = merged
    if original.get("image_display_mode") == "crop_fill" or original.get("portrait_image_mode") == "rotate":
        cfg["image_display_mode"] = "fit_background"
    # Loại bỏ cấu hình converter cũ; V1.2.3 chỉ sử dụng LibreOffice soffice.exe.
    for obsolete in ("wps_path", "wpsoffice_path", "microsoft_office_enabled", "office_com_enabled",
                     "converter_priority", "converter_type", "office_converter_type",
                     "portrait_image_mode", "portrait_rotate_direction"):
        cfg.pop(obsolete, None)
    old_converter = str(original.get("office_converter_path", ""))
    cfg.pop("office_converter_path", None)
    if Path(old_converter).name.casefold() == "soffice.exe" and not cfg.get("libreoffice_path"):
        cfg["libreoffice_path"] = old_converter
    if Path(str(cfg.get("libreoffice_path", ""))).name.casefold() != "soffice.exe":
        cfg["libreoffice_path"] = ""
    if original.get("media_folder") and not original.get("source_folder"):
        cfg["source_folder"] = original["media_folder"]
        cfg["play_folder"] = original["media_folder"] + "_PLAY"
    changed = cfg != original
    for key in ("vlc_path", "media_folder", "source_folder", "play_folder", "libreoffice_path"):
        if cfg.get(key):
            normalized = os.path.normpath(cfg[key])
            if normalized != cfg[key]:
                cfg[key] = normalized
                changed = True
    if changed:
        save_config(cfg)

    return cfg


def save_config(cfg: dict):
    save_encrypted_json(CONFIG_PATH, cfg, "config")


def _natural_key(value):
    return [int(x) if x.isdigit() else x.casefold() for x in re.split(r"(\d+)", value)]


def scan_media_files(folder: str, recursive=False):
    """Quét ảnh/video trong PLAY và bỏ qua file đang copy dở."""
    files = []
    if not folder or not os.path.isdir(folder):
        return files
    root = Path(folder).resolve()
    iterator = root.rglob("*") if recursive else root.glob("*")
    for path in iterator:
        if path.is_file() and path.suffix.lower() in MEDIA_EXT and ".atg_tmp_" not in path.name:
            files.append(str(path.resolve()))
    return sorted(files, key=lambda p: _natural_key(str(Path(p).relative_to(root))))


def build_playlist_file(folder: str, playlist_path: str = PLAYLIST_PATH, recursive=True):
    """Tạo file playlist .m3u từ danh sách media trong thư mục."""
    files = scan_media_files(folder, recursive=recursive)
    temp = playlist_path + ".tmp"
    with open(temp, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for path in files:
            f.write(Path(path).resolve().as_uri() + "\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp, playlist_path)
    return files


def resource_log(message: str):
    try:
        logger = logging.getLogger(APP_NAME)
        if not logger.handlers:
            logger.setLevel(logging.INFO)
            handler = RotatingFileHandler(
                os.path.join(APP_DIR, "log.txt"), maxBytes=5 * 1024 * 1024,
                backupCount=5, encoding="utf-8",
            )
            handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
            logger.addHandler(handler)
            logger.propagate = False
        logger.info(message.rstrip())
    except Exception:
        pass
