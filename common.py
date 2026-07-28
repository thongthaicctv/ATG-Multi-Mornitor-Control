# -*- coding: utf-8 -*-
"""
Các hàm dùng chung cho toàn bộ chương trình VLC Signage.
"""
import json
import os
import sys

from secure_storage import load_encrypted_json, save_encrypted_json


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

VIDEO_EXT = {".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".mpg", ".mpeg", ".m4v", ".ts"}
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp"}
MEDIA_EXT = VIDEO_EXT | IMAGE_EXT


DEFAULT_CONFIG = {
    "vlc_path": r"C:\Program Files\VideoLAN\VLC\vlc.exe",
    "media_folder": r"C:\Signage\Videos",
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
    changed = False
    for key in ("vlc_path", "media_folder"):
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


def scan_media_files(folder: str):
    """Quét toàn bộ file media hợp lệ trong thư mục (không đệ quy con nếu muốn giữ thứ tự đơn giản)."""
    files = []
    if not folder or not os.path.isdir(folder):
        return files
    for name in sorted(os.listdir(folder)):
        path = os.path.normpath(os.path.join(folder, name))
        if os.path.isfile(path):
            ext = os.path.splitext(name)[1].lower()
            if ext in MEDIA_EXT:
                files.append(path)
    return files


def build_playlist_file(folder: str, playlist_path: str = PLAYLIST_PATH):
    """Tạo file playlist .m3u từ danh sách media trong thư mục."""
    files = scan_media_files(folder)
    with open(playlist_path, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for path in files:
            f.write(path + "\n")
    return files


def resource_log(message: str):
    """Ghi log đơn giản ra file log.txt cạnh chương trình (hữu ích khi chạy ẩn/không có console)."""
    log_path = os.path.join(APP_DIR, "log.txt")
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(message.rstrip() + "\n")
    except Exception:
        pass
