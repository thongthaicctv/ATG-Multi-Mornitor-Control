# -*- coding: utf-8 -*-
"""
launcher.pyw
Chương trình chạy nền (không hiện console vì đuôi .pyw):
- Đọc config.atg đã mã hóa
- Tạo playlist từ thư mục media
- Khởi động VLC với tham số phù hợp (repeat all, thời gian ảnh, fullscreen)
- Theo dõi thư mục, khi có thay đổi -> tự làm mới playlist trong VLC qua HTTP interface

Yêu cầu cài đặt (chạy 1 lần):
    pip install watchdog requests

Chạy chương trình:
    pythonw.exe launcher.pyw
(dùng pythonw.exe để không hiện cửa sổ đen console)
"""
import os
import sys
import subprocess
import time
import threading
import base64
import urllib.request
import urllib.parse

from common import (
    load_config, build_playlist_file, scan_media_files,
    resource_log, PLAYLIST_PATH
)
import license_manager
from sync_engine import sync_source_to_play, validate_folder_layout

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False

IS_WINDOWS = sys.platform.startswith("win")
TRIAL_SECONDS = 120  # 2 phút - thời gian chạy tối đa khi chưa có license hợp lệ
LICENSE_RECHECK_SECONDS = 60

CONTACT_COMPANY = "CÔNG TY TNHH CÔNG NGHỆ VÀ THƯƠNG MẠI AN NGUYÊN"
CONTACT_PHONE = "0932 333 000"
CONTACT_EMAIL = "annguyentechcons@gmail.com"
CONTACT_WEBSITES = "https://annguyen.pro/  |  https://camerathainguyen.com/  |  Hotline: 0932 333 000"

vlc_process = None
cfg = load_config()
sync_lock = threading.Lock()
sync_pending = threading.Event()


def show_message_box(title: str, message: str):
    """Hiện hộp thoại thông báo cho người dùng (không cần chạy Tkinter mainloop nền)."""
    if IS_WINDOWS:
        try:
            import ctypes
            MB_OK = 0x0
            MB_ICONWARNING = 0x30
            MB_TOPMOST = 0x40000
            ctypes.windll.user32.MessageBoxW(0, message, title, MB_OK | MB_ICONWARNING | MB_TOPMOST)
            return
        except Exception as e:
            resource_log(f"[MSGBOX] Loi hien MessageBoxW: {e}")
    # Fallback cho hệ điều hành khác Windows (vd môi trường dev/test)
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showwarning(title, message)
        root.destroy()
    except Exception as e:
        resource_log(f"[MSGBOX] Khong the hien thong bao: {e}")


def _upgrade_message(reason: str, trial_ended: bool = False):
    heading = (
        "Thời gian dùng thử 2 phút đã kết thúc."
        if trial_ended else
        "License không còn hiệu lực. Chương trình đã dừng."
    )
    return (
        f"{heading}\n\n"
        "Vui lòng liên hệ quản trị để được hỗ trợ nâng cấp/gia hạn License:\n\n"
        f"{CONTACT_COMPANY}\n"
        f"Điện thoại: {CONTACT_PHONE}\n"
        f"Email: {CONTACT_EMAIL}\n"
        f"Website: {CONTACT_WEBSITES}\n\n"
        f"Thông tin kiểm tra: {reason}"
    )


def _stop_vlc():
    global vlc_process
    if vlc_process is not None:
        try:
            vlc_process.terminate()
        except Exception:
            pass


def enforce_trial_limit(reason: str):
    """
    Chạy trong luồng riêng: chờ TRIAL_SECONDS giây rồi dừng VLC, hiện thông báo
    yêu cầu nâng cấp, và thoát toàn bộ chương trình.
    """
    resource_log(f"[TRIAL] Che do dung thu - ly do: {reason}. Se tu dong dung sau {TRIAL_SECONDS} giay.")
    time.sleep(TRIAL_SECONDS)

    resource_log("[TRIAL] Het thoi gian dung thu, dang dung VLC...")
    _stop_vlc()

    show_message_box(
        "ATG Signage — Hết thời gian dùng thử",
        _upgrade_message(reason, trial_ended=True),
    )
    resource_log("[TRIAL] Da hien thong bao, thoat chuong trinh.")
    os._exit(0)  # thoát ngay lập tức toàn bộ tiến trình, kể cả các luồng nền khác


def vlc_http_request(path_query: str):
    """Gọi VLC HTTP interface để điều khiển playlist đang chạy."""
    port = cfg.get("http_port", 8080)
    password = cfg.get("http_password", "")
    url = f"http://127.0.0.1:{port}/requests/{path_query}"
    req = urllib.request.Request(url)
    token = base64.b64encode(f":{password}".encode("utf-8")).decode("utf-8")
    req.add_header("Authorization", f"Basic {token}")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.read()
    except Exception as e:
        resource_log(f"[HTTP] Loi goi VLC HTTP API: {e}")
        return None


def _is_hard_license_failure(message: str):
    """Các lỗi này không được cấp thêm phiên demo."""
    message = (message or "").casefold()
    markers = (
        "đã hết hạn",
        "đã bị khóa",
        "gắn cho máy khác",
        "mã máy không khớp",
        "ngày hết hạn",
        "đã vượt quá thời gian chạy offline",
        "đồng hồ hệ thống đã bị lùi",
    )
    return any(marker in message for marker in markers)


def monitor_license():
    """Xác minh lại định kỳ để thay đổi trên Google Sheet có hiệu lực khi app đang chạy."""
    while True:
        time.sleep(LICENSE_RECHECK_SECONDS)
        is_valid, message = license_manager.validate_license(cfg)
        if is_valid:
            resource_log(f"[LICENSE] Kiem tra dinh ky OK: {message}")
            continue
        resource_log(f"[LICENSE] Bi thu hoi/het han khi dang chay: {message}")
        _stop_vlc()
        show_message_box(
            "ATG Signage — License không còn hiệu lực",
            _upgrade_message(message),
        )
        os._exit(0)


def refresh_vlc_playlist():
    """Xoá playlist hiện tại trong VLC và nạp lại danh sách media mới nhất từ thư mục."""
    files = build_playlist_file(cfg["play_folder"], recursive=True)
    resource_log(f"[REFRESH] Tim thay {len(files)} file media, dang nap lai vao VLC...")

    # Xoá playlist hiện tại
    vlc_http_request("status.xml?command=pl_empty")

    # Thêm từng file vào playlist
    for path in files:
        encoded = urllib.parse.quote(__import__("pathlib").Path(path).resolve().as_uri(), safe=":/")
        vlc_http_request(f"status.xml?command=in_enqueue&input={encoded}")

    # Bắt đầu phát lại từ đầu
    vlc_http_request("status.xml?command=pl_play")
    resource_log("[REFRESH] Da lam moi playlist xong.")


def perform_sync_and_refresh():
    if not sync_lock.acquire(blocking=False):
        sync_pending.set()
        return
    try:
        while True:
            sync_pending.clear()
            result = sync_source_to_play(cfg["source_folder"], cfg["play_folder"], cfg)
            resource_log(
                f"[SYNC] copied={result.copied} converted={result.converted} "
                f"unchanged={result.unchanged} failed={result.failed}"
            )
            refresh_vlc_playlist()
            if not sync_pending.is_set():
                break
    except Exception as exc:
        resource_log(f"[SYNC] Loi dong bo nen: {exc}")
    finally:
        sync_lock.release()


def build_vlc_args():
    """
    Chỉ dùng các option đã xác nhận hợp lệ trên mọi bản VLC gần đây.
    LƯU Ý QUAN TRỌNG: các option kiểu boolean (--fullscreen, --loop...) trong VLC
    KHÔNG được viết dạng --option=value (vd --play-and-exit=no là SAI cú pháp và
    sẽ làm VLC báo lỗi "could not start / invalid command line options").
    Muốn tắt 1 option boolean thì dùng tiền tố --no-, ví dụ --no-fullscreen.
    """
    vlc_path = cfg["vlc_path"]
    args = [vlc_path]

    # Nạp playlist ban đầu
    args.append(PLAYLIST_PATH)

    # Lặp lại toàn bộ playlist (chỉ cần --loop là đủ, không cần thêm --repeat)
    if cfg.get("repeat_all", True):
        args.append("--loop")

    # Thời gian hiển thị mỗi ảnh (giây) - option dạng key=value, KHÔNG phải boolean nên hợp lệ
    args.append(f"--image-duration={cfg.get('image_duration', 10)}")

    # Toàn màn hình
    if cfg.get("fullscreen", True):
        args.append("--fullscreen")

    # Không hiện tiêu đề video đè lên màn hình
    args.append("--no-video-title-show")

    # Bật HTTP interface để điều khiển từ xa / làm mới playlist
    args.append("--extraintf=http")
    args.append(f"--http-host=127.0.0.1")
    args.append(f"--http-port={cfg.get('http_port', 8080)}")
    args.append(f"--http-password={cfg.get('http_password', 'signage123')}")

    return args


def start_vlc():
    global vlc_process
    build_playlist_file(cfg["play_folder"], recursive=True)
    args = build_vlc_args()
    safe_args = ["--http-password=***" if a.startswith("--http-password=") else a for a in args]
    resource_log(f"[START] Khoi dong VLC voi lenh: {' '.join(safe_args)}")
    try:
        vlc_dir = os.path.dirname(cfg["vlc_path"])
        vlc_env = os.environ.copy()
        vlc_env["VLC_PLUGIN_PATH"] = os.path.join(vlc_dir, "plugins")
        vlc_env["PATH"] = vlc_dir + os.pathsep + vlc_env.get("PATH", "")
        vlc_process = subprocess.Popen(
            args,
            cwd=vlc_dir,
            env=vlc_env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        resource_log(f"[ERROR] Khong tim thay file vlc.exe tai duong dan: {vlc_path_hint()}")
        raise
    return vlc_process


def vlc_path_hint():
    return cfg.get("vlc_path", "(chua cau hinh)")


class FolderChangeHandler(FileSystemEventHandler):
    """Bắt sự kiện thay đổi trong thư mục media và làm mới playlist (có chống dội - debounce)."""

    def __init__(self):
        self._timer = None
        self._lock = threading.Lock()

    def _trigger_refresh(self):
        with self._lock:
            if self._timer:
                self._timer.cancel()
            self._timer = threading.Timer(
                float(cfg.get("sync_debounce_seconds", 3)), perform_sync_and_refresh
            )
            self._timer.start()

    def on_created(self, event):
        resource_log(f"[WATCH] Phat hien file moi: {event.src_path}")
        self._trigger_refresh()

    def on_deleted(self, event):
        resource_log(f"[WATCH] Phat hien file bi xoa: {event.src_path}")
        self._trigger_refresh()

    def on_moved(self, event):
        resource_log(f"[WATCH] Phat hien file duoc di chuyen/doi ten: {event.src_path}")
        self._trigger_refresh()


def watch_folder():
    if not WATCHDOG_AVAILABLE:
        resource_log("[WATCH] Thu vien watchdog chua duoc cai, chuyen sang che do kiem tra dinh ky.")
        watch_folder_polling()
        return

    handler = FolderChangeHandler()
    observer = Observer()
    observer.schedule(handler, cfg["source_folder"], recursive=cfg.get("recursive_scan", True))
    observer.start()
    resource_log("[WATCH] Dang theo doi thay doi thu muc (watchdog).")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


def watch_folder_polling():
    """Phương án dự phòng nếu chưa cài watchdog: kiểm tra định kỳ danh sách file."""
    from pathlib import Path
    source = Path(cfg["source_folder"])
    last_snapshot = {(str(p), p.stat().st_size, p.stat().st_mtime_ns) for p in source.rglob("*") if p.is_file()}
    interval = cfg.get("watch_interval_seconds", 5)
    while True:
        time.sleep(interval)
        current = {(str(p), p.stat().st_size, p.stat().st_mtime_ns) for p in source.rglob("*") if p.is_file()}
        if current != last_snapshot:
            resource_log("[WATCH-POLL] Phat hien thay doi thu muc, lam moi playlist.")
            perform_sync_and_refresh()
            last_snapshot = current


def validate_config():
    """Kiểm tra config trước khi chạy, log rõ nguyên nhân nếu sai để dễ debug."""
    problems = []
    if not os.path.exists(cfg.get("vlc_path", "")):
        problems.append(f"Khong tim thay vlc.exe tai: {cfg.get('vlc_path')}")
    try:
        source, play = validate_folder_layout(cfg.get("source_folder", ""), cfg.get("play_folder", ""))
        if not source.is_dir():
            problems.append(f"Thu muc SOURCE khong ton tai: {source}")
        play.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        problems.append(str(exc))

    if problems:
        for p in problems:
            resource_log(f"[VALIDATE] LOI: {p}")
        raise RuntimeError("Cau hinh chua hop le, xem chi tiet trong log.txt:\n" + "\n".join(problems))

    resource_log("[VALIDATE] OK - SOURCE/PLAY an toan.")


def main():
    resource_log("=" * 50)
    resource_log("[MAIN] Khoi dong chuong trinh VLC Signage")

    validate_config()

    # ---- Kiểm tra License ----
    is_valid, license_msg = license_manager.validate_license(cfg)
    if is_valid:
        resource_log(f"[LICENSE] OK: {license_msg}")
    else:
        resource_log(f"[LICENSE] KHONG HOP LE: {license_msg}")

    if not is_valid and _is_hard_license_failure(license_msg):
        show_message_box(
            "ATG Signage — License không còn hiệu lực",
            _upgrade_message(license_msg),
        )
        resource_log("[LICENSE] Tu choi khoi dong do license het han/bi khoa/sai may.")
        return

    if cfg.get("sync_on_startup", True) and "--skip-sync" not in sys.argv:
        delay = max(0, int(cfg.get("startup_delay_seconds", 10)))
        if delay:
            resource_log(f"[SYNC] Cho {delay}s truoc khi dong bo khoi dong.")
            time.sleep(delay)
        deadline = time.time() + 120
        while not os.path.isdir(cfg["source_folder"]) and time.time() < deadline:
            resource_log("[SYNC] SOURCE chua san sang, thu lai sau 5s.")
            time.sleep(5)
        if os.path.isdir(cfg["source_folder"]):
            try:
                sync_source_to_play(cfg["source_folder"], cfg["play_folder"], cfg)
            except Exception as exc:
                resource_log(f"[SYNC] Dong bo khoi dong loi, thu phat PLAY cu: {exc}")

    play_files = scan_media_files(cfg["play_folder"], recursive=True)
    if not play_files:
        show_message_box(
            "ATG Signage — Không có nội dung",
            "Thư mục PLAY chưa có ảnh hoặc video hợp lệ. Vui lòng kiểm tra SOURCE và đồng bộ lại.",
        )
        resource_log("[MAIN] PLAY rong, khong khoi dong VLC.")
        return

    proc = start_vlc()

    if not is_valid:
        # Chưa có license hợp lệ -> cho chạy thử TRIAL_SECONDS giây rồi tự tắt + báo cần nâng cấp
        trial_thread = threading.Thread(target=enforce_trial_limit, args=(license_msg,), daemon=True)
        trial_thread.start()
    else:
        license_thread = threading.Thread(target=monitor_license, daemon=True)
        license_thread.start()

    # Đợi 1.5s rồi kiểm tra ngay xem VLC có thoát đột ngột không (báo lỗi command line)
    time.sleep(1.5)
    if proc.poll() is not None:
        # Tiến trình đã kết thúc ngay lập tức -> chắc chắn có lỗi
        resource_log(f"[ERROR] VLC thoat ngay lap tuc (exit code {proc.returncode}).")
        raise RuntimeError(
            "VLC thoat ngay sau khi khoi dong. Kiem tra chi tiet trong file log.txt "
            "(thuong do duong dan vlc.exe sai, playlist rong, hoac tham so dong lenh khong hop le)."
        )

    # Đợi VLC khởi động xong HTTP interface trước khi có thể điều khiển
    time.sleep(1.5)

    # Chạy theo dõi thư mục ở luồng chính (chương trình sẽ chạy mãi tới khi VLC bị đóng)
    watch_thread = threading.Thread(target=watch_folder, daemon=True)
    watch_thread.start()

    # Nếu VLC bị đóng, thoát chương trình theo
    proc.wait()
    resource_log("[MAIN] VLC da dong, thoat chuong trinh.")


if __name__ == "__main__":
    main()
