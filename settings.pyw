# -*- coding: utf-8 -*-
"""
settings.pyw
Giao diện cấu hình cho VLC Signage.
Chạy file này bằng: pythonw.exe settings.pyw  (hoặc python settings.pyw để xem log lỗi nếu có)
"""
import os
import sys
import subprocess
import threading
import tkinter as tk
import webbrowser
from tkinter import ttk, filedialog, messagebox

from PIL import Image, ImageTk

from common import load_config, save_config, APP_DIR, RESOURCE_DIR
from hardware_identity import get_machine_code
import license_manager
from sync_engine import (sync_source_to_play, validate_folder_layout,
                         find_libreoffice_executable, LibreOfficeConverter)

IS_WINDOWS = sys.platform.startswith("win")

ASSETS_DIR = os.path.join(RESOURCE_DIR, "assets")
ICON_PATH = os.path.join(ASSETS_DIR, "app_icon.ico")
BANNER_PATH = os.path.join(ASSETS_DIR, "banner_header.png")

TASK_SHUTDOWN = "VLCSignage_Shutdown"
TASK_RESTART = "VLCSignage_Restart"
RUN_KEY_NAME = "VLCSignage"
WINDOWS_APP_ID = "AnNguyen.ATGSignage.Settings.1"

COMPANY_NAME = "CÔNG TY TNHH CÔNG NGHỆ VÀ THƯƠNG MẠI AN NGUYÊN"
COMPANY_WEBSITES = (
    ("annguyen.pro", "https://annguyen.pro/"),
    ("camerathainguyen.com", "https://camerathainguyen.com/"),
    ("hotline 0932 333 000", "https://camerathainguyen.com/"),
    )
COMPANY_HANOI = "Trụ sở Hà Nội: Số 66 Ngõ 328 đường Tây Mỗ, P. Tây Mỗ, TP Hà Nội, Việt Nam"
COMPANY_THAINGUYEN = (
    "Chi nhánh Thái Nguyên: Số 202 đường Thống Nhất, "
    "P. Phan Đình Phùng, T. Thái Nguyên"
)


def get_launcher_command():
    """
    Trả về (list_args) để khởi động launcher, tự nhận biết đang chạy dạng
    file .exe đã build (PyInstaller) hay đang chạy trực tiếp bằng Python (dev).
    """
    if getattr(sys, "frozen", False):
        # Bản one-file dùng chính EXE hiện tại với chế độ launcher.
        return [sys.executable, "--launcher"]
    else:
        launcher_path = os.path.join(APP_DIR, "launcher.pyw")
        pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
        if not os.path.exists(pythonw):
            pythonw = "pythonw.exe"
        return [pythonw, launcher_path]


# ---------------------- Windows: Khởi động cùng Win ----------------------

def set_run_on_startup(enable: bool):
    if not IS_WINDOWS:
        return
    import winreg
    command = " ".join(f'"{p}"' for p in get_launcher_command())

    key = winreg.OpenKey(
        winreg.HKEY_CURRENT_USER,
        r"Software\Microsoft\Windows\CurrentVersion\Run",
        0, winreg.KEY_SET_VALUE
    )
    try:
        if enable:
            winreg.SetValueEx(key, RUN_KEY_NAME, 0, winreg.REG_SZ, command)
        else:
            try:
                winreg.DeleteValue(key, RUN_KEY_NAME)
            except FileNotFoundError:
                pass
    finally:
        winreg.CloseKey(key)


# ---------------------- Windows: Lịch tắt / khởi động lại máy ----------------------

def set_scheduled_task(task_name: str, enable: bool, time_str: str, action: str):
    """
    action: 'shutdown' hoặc 'restart'
    time_str: 'HH:MM'
    """
    if not IS_WINDOWS:
        return

    # Xoá task cũ nếu có (để cập nhật giờ mới)
    subprocess.run(
        ["schtasks", "/Delete", "/TN", task_name, "/F"],
        capture_output=True
    )

    if not enable:
        return

    if action == "shutdown":
        cmd = "shutdown /s /f /t 0"
    else:
        cmd = "shutdown /r /f /t 0"

    result = subprocess.run(
        [
            "schtasks", "/Create", "/TN", task_name,
            "/TR", cmd,
            "/SC", "DAILY",
            "/ST", time_str,
            "/RL", "HIGHEST",
            "/F"
        ],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr or result.stdout)


# ---------------------- Giao diện ----------------------

class SettingsApp(tk.Tk):
    def __init__(self):
        if IS_WINDOWS:
            try:
                # Tách ứng dụng khỏi python.exe để Windows dùng icon EXE trên taskbar.
                import ctypes
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(WINDOWS_APP_ID)
            except Exception:
                pass
        super().__init__()
        self.title("Cấu hình ATG Multi Mornitor Control V1.2.4 — https://annguyen.pro")
        self.geometry("900x760")
        self.minsize(780, 600)
        self.resizable(True, True)

        self._set_window_icon()
        self.after(100, self._set_window_icon)

        self.cfg = load_config()
        self._build_ui()
        self._load_values()

    def _set_window_icon(self):
        try:
            if os.path.exists(ICON_PATH):
                self.iconbitmap(ICON_PATH)
                self.wm_iconbitmap(ICON_PATH)
        except Exception:
            pass  # một số hệ thống không hỗ trợ .ico (vd macOS/Linux) -> bỏ qua, không ảnh hưởng chức năng

    @staticmethod
    def _open_url(url):
        webbrowser.open_new_tab(url)

    def _build_company_banner(self, parent):
        banner = tk.Frame(parent, bg="#24143f", highlightthickness=1, highlightbackground="#4b2b73")
        banner.columnconfigure(1, weight=1)

        if os.path.exists(BANNER_PATH):
            try:
                image = Image.open(BANNER_PATH).convert("RGBA")
                image.thumbnail((180, 180), Image.Resampling.LANCZOS)
                self.banner_img = ImageTk.PhotoImage(image)
                tk.Label(
                    banner, image=self.banner_img, bg="#17101c", padx=10, pady=10
                ).grid(row=0, column=0, rowspan=5, sticky="nsew")
            except Exception:
                pass

        info = tk.Frame(banner, bg="#24143f")
        info.grid(row=0, column=1, sticky="nsew", padx=22, pady=15)
        info.columnconfigure(0, weight=1)

        tk.Label(
            info, text=COMPANY_NAME, bg="#24143f", fg="white",
            font=("Segoe UI", 15, "bold"), anchor="w", justify="left",
            wraplength=620,
        ).grid(row=0, column=0, sticky="ew")
        tk.Label(
            info, text="GIẢI PHÁP PHÁT NỘI DUNG ĐA MÀN HÌNH",
            bg="#24143f", fg="#55b9ff", font=("Segoe UI", 10, "bold"),
            anchor="w",
        ).grid(row=1, column=0, sticky="ew", pady=(3, 7))

        website_frame = tk.Frame(info, bg="#24143f")
        website_frame.grid(row=2, column=0, sticky="w", pady=(0, 7))
        for index, (caption, url) in enumerate(COMPANY_WEBSITES):
            if index:
                tk.Label(
                    website_frame, text="  •  ", bg="#24143f", fg="#d5cae5"
                ).pack(side="left")
            link = tk.Label(
                website_frame, text=caption, bg="#24143f", fg="#64c8ff",
                cursor="hand2", font=("Segoe UI", 9, "underline"),
            )
            link.pack(side="left")
            link.bind("<Button-1>", lambda _event, target=url: self._open_url(target))

        for row_index, text in enumerate((COMPANY_HANOI, COMPANY_THAINGUYEN), start=3):
            tk.Label(
                info, text=text, bg="#24143f", fg="#e5dfeb",
                font=("Segoe UI", 9), anchor="w", justify="left",
                wraplength=620,
            ).grid(row=row_index, column=0, sticky="ew", pady=1)
        return banner

    def _build_ui(self):
        pad = {"padx": 10, "pady": 6}

        # ---- Vùng cuộn (scrollable) để nội dung KHÔNG BAO GIỜ bị che dù cửa sổ nhỏ ----
        outer = ttk.Frame(self)
        outer.pack(fill="both", expand=True)

        canvas = tk.Canvas(outer, highlightthickness=0)
        vscroll = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vscroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        vscroll.pack(side="right", fill="y")

        frm = ttk.Frame(canvas)
        frm_window = canvas.create_window((0, 0), window=frm, anchor="nw")

        def _on_frame_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _on_canvas_resize(event):
            canvas.itemconfig(frm_window, width=event.width)

        frm.bind("<Configure>", _on_frame_configure)
        canvas.bind("<Configure>", _on_canvas_resize)

        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # Cho phép cột chứa Entry giãn theo chiều rộng cửa sổ
        frm.columnconfigure(1, weight=1)

        # ---- Banner công ty đầu trang ----
        row = 0
        self._build_company_banner(frm).grid(
            row=row, column=0, columnspan=3, sticky="ew", padx=10, pady=(10, 8)
        )
        row += 1
        ttk.Label(frm, text="Đường dẫn VLC (vlc.exe):").grid(row=row, column=0, sticky="w", **pad)
        self.var_vlc = tk.StringVar()
        ttk.Entry(frm, textvariable=self.var_vlc, width=45).grid(row=row, column=1, **pad)
        ttk.Button(frm, text="Chọn...", command=self._browse_vlc).grid(row=row, column=2, **pad)

        row += 1
        ttk.Label(frm, text="Thư mục nguồn (ảnh/video/PDF/Office):").grid(row=row, column=0, sticky="w", **pad)
        self.var_source_folder = tk.StringVar()
        ttk.Entry(frm, textvariable=self.var_source_folder, width=45).grid(row=row, column=1, **pad)
        source_buttons = ttk.Frame(frm)
        source_buttons.grid(row=row, column=2, **pad)
        ttk.Button(source_buttons, text="Chọn...", command=lambda: self._browse_folder(self.var_source_folder)).pack(side="left")
        ttk.Button(source_buttons, text="Mở", command=lambda: self._open_folder(self.var_source_folder.get())).pack(side="left", padx=3)

        row += 1
        ttk.Label(frm, text="Thư mục PLAY (dữ liệu đã xử lý):").grid(row=row, column=0, sticky="w", **pad)
        self.var_play_folder = tk.StringVar()
        ttk.Entry(frm, textvariable=self.var_play_folder, width=45).grid(row=row, column=1, **pad)
        play_buttons = ttk.Frame(frm)
        play_buttons.grid(row=row, column=2, **pad)
        ttk.Button(play_buttons, text="Chọn...", command=lambda: self._browse_folder(self.var_play_folder)).pack(side="left")
        ttk.Button(play_buttons, text="Mở", command=lambda: self._open_folder(self.var_play_folder.get())).pack(side="left", padx=3)

        row += 1
        ttk.Label(frm, text="Đường dẫn LibreOffice:").grid(row=row, column=0, sticky="w", **pad)
        self.var_libreoffice = tk.StringVar()
        ttk.Entry(frm, textvariable=self.var_libreoffice, width=45).grid(row=row, column=1, **pad)
        lo_buttons = ttk.Frame(frm)
        lo_buttons.grid(row=row, column=2, **pad)
        ttk.Button(lo_buttons, text="CHỌN SOFFICE.EXE", command=self._browse_libreoffice).pack(side="left")
        ttk.Button(lo_buttons, text="TỰ ĐỘNG TÌM", command=self._auto_find_libreoffice).pack(side="left", padx=3)
        ttk.Button(lo_buttons, text="KIỂM TRA", command=self._test_libreoffice).pack(side="left")
        row += 1
        ttk.Label(frm, text=r"Thường cài tại C:\Program Files\LibreOffice\program\soffice.exe (hoặc Program Files (x86)).",
                  foreground="#666666").grid(row=row, column=0, columnspan=3, sticky="w", padx=10)

        row += 1
        options = ttk.Frame(frm)
        options.grid(row=row, column=0, columnspan=3, sticky="w", **pad)
        ttk.Label(options, text="DPI tài liệu:").pack(side="left")
        self.var_pdf_dpi = tk.IntVar()
        ttk.Spinbox(options, from_=72, to=300, textvariable=self.var_pdf_dpi, width=6).pack(side="left", padx=(4, 14))
        self.var_recursive_scan = tk.BooleanVar()
        ttk.Checkbutton(options, text="Quét thư mục con", variable=self.var_recursive_scan).pack(side="left")
        self.var_remove_deleted = tk.BooleanVar()
        ttk.Checkbutton(options, text="Xóa output khi nguồn đã xóa", variable=self.var_remove_deleted).pack(side="left", padx=8)
        self.var_sync_startup = tk.BooleanVar()
        ttk.Checkbutton(options, text="Đồng bộ khi khởi động", variable=self.var_sync_startup).pack(side="left")

        row += 1
        orientation = ttk.LabelFrame(frm, text="CHẾ ĐỘ HIỂN THỊ ẢNH VÀ TÀI LIỆU")
        orientation.grid(row=row, column=0, columnspan=3, sticky="ew", padx=10, pady=6)
        self.var_image_display_mode = tk.StringVar()
        ttk.Radiobutton(orientation, text="Full màn hình – giữ đủ nội dung", variable=self.var_image_display_mode,
                        value="fit_background", command=self._update_crop_controls).grid(row=0, column=0, sticky="w", padx=8, pady=4)
        ttk.Label(orientation, text="Giữ toàn bộ nội dung ở giữa; phần trống được lấp bằng nền mở rộng.",
                  foreground="#666666").grid(row=1, column=0, sticky="w", padx=28)
        ttk.Radiobutton(orientation, text="Phát nguyên ảnh", variable=self.var_image_display_mode,
                        value="original", command=self._update_crop_controls).grid(row=2, column=0, sticky="w", padx=8, pady=4)
        ttk.Radiobutton(orientation, text="Kéo giãn toàn màn hình (có thể làm méo ảnh)", variable=self.var_image_display_mode,
                        value="stretch_fill", command=self._update_crop_controls).grid(row=3, column=0, sticky="w", padx=8, pady=4)
        self.crop_options = ttk.Frame(orientation)
        self.crop_options.grid(row=4, column=0, sticky="w", padx=28)
        ttk.Label(self.crop_options, text="Kích thước:").pack(side="left")
        self.var_crop_width = tk.IntVar()
        self.var_crop_height = tk.IntVar()
        ttk.Spinbox(self.crop_options, from_=320, to=7680, textvariable=self.var_crop_width, width=7).pack(side="left", padx=4)
        ttk.Label(self.crop_options, text="×").pack(side="left")
        ttk.Spinbox(self.crop_options, from_=240, to=4320, textvariable=self.var_crop_height, width=7).pack(side="left", padx=4)
        self.var_photo_background_style = tk.StringVar()
        self.var_document_background_style = tk.StringVar()
        ttk.Label(self.crop_options, text="Nền ảnh:").pack(side="left", padx=(16, 3))
        ttk.Radiobutton(self.crop_options, text="Mờ", variable=self.var_photo_background_style, value="blur").pack(side="left")
        ttk.Radiobutton(self.crop_options, text="Đơn sắc", variable=self.var_photo_background_style, value="solid").pack(side="left")
        ttk.Label(self.crop_options, text="Nền tài liệu:").pack(side="left", padx=(16, 3))
        ttk.Radiobutton(self.crop_options, text="Trắng", variable=self.var_document_background_style, value="solid").pack(side="left")
        ttk.Radiobutton(self.crop_options, text="Mờ", variable=self.var_document_background_style, value="blur").pack(side="left")
        self.var_normalize_orientation = tk.BooleanVar()
        ttk.Checkbutton(orientation, text="Chuẩn hóa hướng ảnh theo EXIF (khuyến nghị)",
                        variable=self.var_normalize_orientation).grid(row=5, column=0, sticky="w", padx=8, pady=4)
        ttk.Label(orientation, text="Ảnh chính luôn được giữ đủ nội dung. Chỉ lớp nền có thể được phóng và crop.",
                  foreground="#a05a00").grid(row=6, column=0, sticky="w", padx=8, pady=(0, 6))

        row += 1
        ttk.Label(frm, text="Thời gian hiển thị mỗi ảnh (giây):").grid(row=row, column=0, sticky="w", **pad)
        self.var_duration = tk.IntVar()
        ttk.Spinbox(frm, from_=1, to=3600, textvariable=self.var_duration, width=10).grid(row=row, column=1, sticky="w", **pad)

        row += 1
        self.var_repeat = tk.BooleanVar()
        ttk.Checkbutton(frm, text="Lặp lại toàn bộ playlist (Repeat All)", variable=self.var_repeat).grid(row=row, column=0, columnspan=2, sticky="w", **pad)

        row += 1
        self.var_fullscreen = tk.BooleanVar()
        ttk.Checkbutton(frm, text="Phát toàn màn hình (Fullscreen)", variable=self.var_fullscreen).grid(row=row, column=0, columnspan=2, sticky="w", **pad)

        row += 1
        ttk.Separator(frm, orient="horizontal").grid(row=row, column=0, columnspan=3, sticky="ew", pady=10)

        row += 1
        self.var_sync_status = tk.StringVar(value="Chưa đồng bộ")
        ttk.Label(frm, textvariable=self.var_sync_status, foreground="#245a85").grid(
            row=row, column=0, columnspan=3, sticky="w", padx=10
        )
        row += 1
        self.sync_progress = ttk.Progressbar(frm, mode="determinate")
        self.sync_progress.grid(row=row, column=0, columnspan=3, sticky="ew", padx=10, pady=(0, 5))

        row += 1
        ttk.Label(frm, text="Mã máy (Copy gửi quản trị):").grid(row=row, column=0, sticky="w", **pad)
        self.var_machine_code = tk.StringVar(value=get_machine_code())
        ttk.Entry(
            frm, textvariable=self.var_machine_code, width=45, state="readonly"
        ).grid(row=row, column=1, sticky="ew", **pad)
        ttk.Button(
            frm, text="Tạo & sao chép", command=self._copy_machine_code
        ).grid(row=row, column=2, **pad)

        row += 1
        ttk.Label(
            frm,
            text="Sao chép mã này về quản trị viên 0932333000 - email : annguyentechcons@gmail.com .",
            foreground="#c0392b"
        ).grid(row=row, column=0, columnspan=3, sticky="w", padx=10)

        row += 1
        ttk.Label(frm, text="License Key:").grid(row=row, column=0, sticky="w", **pad)
        self.var_license_key = tk.StringVar()
        ttk.Entry(frm, textvariable=self.var_license_key, width=45).grid(row=row, column=1, sticky="w", **pad)
        ttk.Button(frm, text="Kiểm tra License", command=self._check_license).grid(row=row, column=2, **pad)

        row += 1
        self.var_license_status = tk.StringVar(value="Chưa kiểm tra")
        self.lbl_license_status = ttk.Label(frm, textvariable=self.var_license_status, foreground="#666666")
        self.lbl_license_status.grid(row=row, column=0, columnspan=3, sticky="w", padx=10)

        row += 1
        ttk.Label(
            frm,
            text="Chưa có License hợp lệ: chương trình sẽ chạy được 2 phút mỗi lần khởi động rồi tự dừng.",
            foreground="#a05a00"
        ).grid(row=row, column=0, columnspan=3, sticky="w", padx=10)

        row += 1
        ttk.Separator(frm, orient="horizontal").grid(row=row, column=0, columnspan=3, sticky="ew", pady=10)

        row += 1
        self.var_startup = tk.BooleanVar()
        ttk.Checkbutton(frm, text="Khởi động cùng Windows", variable=self.var_startup).grid(row=row, column=0, columnspan=2, sticky="w", **pad)

        row += 1
        ttk.Separator(frm, orient="horizontal").grid(row=row, column=0, columnspan=3, sticky="ew", pady=10)

        row += 1
        self.var_shutdown_enabled = tk.BooleanVar()
        ttk.Checkbutton(frm, text="Tự động TẮT máy lúc:", variable=self.var_shutdown_enabled).grid(row=row, column=0, sticky="w", **pad)
        self.var_shutdown_time = tk.StringVar()
        ttk.Entry(frm, textvariable=self.var_shutdown_time, width=10).grid(row=row, column=1, sticky="w", **pad)

        row += 1
        ttk.Label(frm, text="(định dạng HH:MM, ví dụ 22:00)", foreground="#666666").grid(
            row=row, column=0, columnspan=2, sticky="w", padx=10
        )

        row += 1
        self.var_restart_enabled = tk.BooleanVar()
        ttk.Checkbutton(frm, text="Tự động KHỞI ĐỘNG LẠI lúc:", variable=self.var_restart_enabled).grid(row=row, column=0, sticky="w", **pad)
        self.var_restart_time = tk.StringVar()
        ttk.Entry(frm, textvariable=self.var_restart_time, width=10).grid(row=row, column=1, sticky="w", **pad)

        row += 1
        ttk.Label(frm, text="(định dạng HH:MM, ví dụ 06:00)", foreground="#666666").grid(
            row=row, column=0, columnspan=2, sticky="w", padx=10
        )

        row += 1
        ttk.Separator(frm, orient="horizontal").grid(row=row, column=0, columnspan=3, sticky="ew", pady=10)

        row += 1
        btn_frame = ttk.Frame(frm)
        btn_frame.grid(row=row, column=0, columnspan=3, pady=10)
        ttk.Button(btn_frame, text="Lưu & Áp dụng", command=self._save).pack(side="left", padx=5)
        self.btn_sync = ttk.Button(btn_frame, text="Đồng bộ ngay", command=self._sync_now)
        self.btn_sync.pack(side="left", padx=5)
        self.btn_sync_play = ttk.Button(btn_frame, text="Đồng bộ và phát", command=self._run_now)
        self.btn_sync_play.pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Phát từ PLAY", command=self._play_only).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Dừng VLC", command=self._stop_vlc).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Thoát", command=self.destroy).pack(side="left", padx=5)

        if not IS_WINDOWS:
            row += 1
            ttk.Label(
                frm,
                text="⚠ Đang chạy trên hệ điều hành khác Windows: chức năng khởi động cùng máy và\n"
                     "lịch tắt/khởi động lại sẽ không hoạt động (chỉ hỗ trợ trên Windows).",
                foreground="red"
            ).grid(row=row, column=0, columnspan=3, sticky="w", **pad)

    def _load_values(self):
        c = self.cfg
        self.var_vlc.set(c.get("vlc_path", ""))
        self.var_source_folder.set(c.get("source_folder", c.get("media_folder", "")))
        self.var_play_folder.set(c.get("play_folder", c.get("media_folder", "") + "_PLAY"))
        self.var_libreoffice.set(c.get("libreoffice_path", ""))
        self.var_pdf_dpi.set(c.get("pdf_dpi", 150))
        self.var_recursive_scan.set(c.get("recursive_scan", True))
        self.var_remove_deleted.set(c.get("remove_deleted_from_play", True))
        self.var_sync_startup.set(c.get("sync_on_startup", True))
        self.var_image_display_mode.set(c.get("image_display_mode", "fit_background"))
        self.var_crop_width.set(c.get("crop_target_width", 1920))
        self.var_crop_height.set(c.get("crop_target_height", 1080))
        self.var_photo_background_style.set(c.get("photo_background_style", "blur"))
        self.var_document_background_style.set(c.get("document_background_style", "solid"))
        self.var_normalize_orientation.set(c.get("normalize_image_orientation", True))
        self._update_crop_controls()
        self.var_duration.set(c.get("image_duration", 10))
        self.var_repeat.set(c.get("repeat_all", True))
        self.var_fullscreen.set(c.get("fullscreen", True))
        self.var_startup.set(c.get("run_on_startup", False))
        self.var_shutdown_enabled.set(c.get("shutdown_enabled", False))
        self.var_shutdown_time.set(c.get("shutdown_time", "22:00"))
        self.var_restart_enabled.set(c.get("restart_enabled", False))
        self.var_restart_time.set(c.get("restart_time", "06:00"))
        self.var_license_key.set(c.get("license_key", ""))

    def _browse_vlc(self):
        path = filedialog.askopenfilename(title="Chọn vlc.exe", filetypes=[("VLC executable", "vlc.exe"), ("All files", "*.*")])
        if path:
            self.var_vlc.set(os.path.normpath(path))

    def _update_crop_controls(self):
        state = "normal" if self.var_image_display_mode.get() == "fit_background" else "disabled"
        for child in self.crop_options.winfo_children():
            child.configure(state=state)

    def _browse_folder(self, variable):
        path = filedialog.askdirectory(title="Chọn thư mục")
        if path:
            variable.set(os.path.normpath(path))

    def _open_folder(self, path):
        if path:
            os.makedirs(path, exist_ok=True)
            os.startfile(path)

    def _browse_libreoffice(self):
        path = filedialog.askopenfilename(
            title="Chọn LibreOffice soffice.exe",
            filetypes=[("LibreOffice", "soffice.exe"), ("Executable", "*.exe")],
        )
        if path:
            if os.path.basename(path).casefold() != "soffice.exe":
                messagebox.showwarning("LibreOffice", "Vui lòng chọn file soffice.exe trong thư mục program của LibreOffice.")
                return
            self.var_libreoffice.set(os.path.normpath(path))

    def _auto_find_libreoffice(self):
        path = find_libreoffice_executable(self.var_libreoffice.get())
        if path:
            self.var_libreoffice.set(str(path))
            self.var_sync_status.set("Đã tìm thấy LibreOffice.")
            return
        self.var_sync_status.set("Chưa tìm thấy LibreOffice. Hãy cài đặt hoặc chọn soffice.exe.")

    def _test_libreoffice(self):
        path = find_libreoffice_executable(self.var_libreoffice.get())
        if not path:
            messagebox.showerror("LibreOffice", "Chưa tìm thấy LibreOffice. Hãy chọn soffice.exe.")
            return
        valid, version = LibreOfficeConverter(path, 15).validate()
        if valid:
            self.var_libreoffice.set(str(path))
            messagebox.showinfo("LibreOffice đã sẵn sàng", f"Phiên bản: {version}\nĐường dẫn: {path}")
        else:
            messagebox.showerror("LibreOffice không hợp lệ", version)

    def _copy_machine_code(self):
        code = get_machine_code()
        self.var_machine_code.set(code)
        self.clipboard_clear()
        self.clipboard_append(code)
        self.update()
        self.var_license_status.set("✓ Đã sao chép Mã máy. Hãy dán vào cột MaMay trên Google Sheet.")
        self.lbl_license_status.configure(foreground="#0a7d2c")

    def _validate_time(self, t: str) -> bool:
        try:
            h, m = t.split(":")
            h, m = int(h), int(m)
            return 0 <= h <= 23 and 0 <= m <= 59
        except Exception:
            return False

    def _save(self, show_success=True):
        if self.var_shutdown_enabled.get() and not self._validate_time(self.var_shutdown_time.get()):
            messagebox.showerror("Lỗi", "Giờ tắt máy không hợp lệ. Định dạng đúng: HH:MM")
            return
        if self.var_restart_enabled.get() and not self._validate_time(self.var_restart_time.get()):
            messagebox.showerror("Lỗi", "Giờ khởi động lại không hợp lệ. Định dạng đúng: HH:MM")
            return
        if not os.path.exists(self.var_vlc.get()):
            if not messagebox.askyesno("Cảnh báo", "Không tìm thấy vlc.exe tại đường dẫn đã chọn. Vẫn tiếp tục lưu?"):
                return
        libreoffice_value = self.var_libreoffice.get().strip()
        if libreoffice_value and (os.path.basename(libreoffice_value).casefold() != "soffice.exe"
                                  or not os.path.isfile(libreoffice_value)):
            messagebox.showerror("LibreOffice", "Đường dẫn không hợp lệ. Vui lòng chọn file soffice.exe.")
            return

        self.cfg.update({
            "vlc_path": os.path.normpath(self.var_vlc.get()),
            "source_folder": os.path.normpath(self.var_source_folder.get()),
            "play_folder": os.path.normpath(self.var_play_folder.get()),
            "libreoffice_path": os.path.normpath(self.var_libreoffice.get()) if self.var_libreoffice.get() else "",
            "pdf_dpi": max(72, min(300, int(self.var_pdf_dpi.get()))),
            "recursive_scan": bool(self.var_recursive_scan.get()),
            "remove_deleted_from_play": bool(self.var_remove_deleted.get()),
            "sync_before_play": True,
            "sync_on_startup": bool(self.var_sync_startup.get()),
            "libreoffice_timeout_seconds": 180,
            "image_display_mode": self.var_image_display_mode.get(),
            "fit_background_style": "auto",
            "photo_background_style": self.var_photo_background_style.get(),
            "document_background_style": self.var_document_background_style.get(),
            "document_background_color": "#FFFFFF",
            "crop_target_mode": "selected_monitor",
            "crop_target_width": max(320, int(self.var_crop_width.get())),
            "crop_target_height": max(240, int(self.var_crop_height.get())),
            "normalize_image_orientation": bool(self.var_normalize_orientation.get()),
            "image_duration": int(self.var_duration.get()),
            "repeat_all": bool(self.var_repeat.get()),
            "fullscreen": bool(self.var_fullscreen.get()),
            "run_on_startup": bool(self.var_startup.get()),
            "shutdown_enabled": bool(self.var_shutdown_enabled.get()),
            "shutdown_time": self.var_shutdown_time.get(),
            "restart_enabled": bool(self.var_restart_enabled.get()),
            "restart_time": self.var_restart_time.get(),
            "license_key": self.var_license_key.get().strip(),
        })
        try:
            os.makedirs(self.cfg["source_folder"], exist_ok=True)
            os.makedirs(self.cfg["play_folder"], exist_ok=True)
        except OSError as exc:
            messagebox.showerror("Thư mục SOURCE/PLAY", f"Không thể tạo thư mục đã chọn: {exc}\nHãy chọn đường dẫn khác.")
            return
        save_config(self.cfg)

        errors = []
        try:
            set_run_on_startup(self.cfg["run_on_startup"])
        except Exception as e:
            errors.append(f"Lỗi cài đặt khởi động cùng Win: {e}")

        try:
            set_scheduled_task(TASK_SHUTDOWN, self.cfg["shutdown_enabled"], self.cfg["shutdown_time"], "shutdown")
        except Exception as e:
            errors.append(f"Lỗi cài đặt lịch tắt máy: {e}")

        try:
            set_scheduled_task(TASK_RESTART, self.cfg["restart_enabled"], self.cfg["restart_time"], "restart")
        except Exception as e:
            errors.append(f"Lỗi cài đặt lịch khởi động lại: {e}")

        if errors:
            messagebox.showwarning("Đã lưu nhưng có lỗi", "\n".join(errors) +
                                    "\n\n(Lưu ý: cần chạy chương trình với quyền Administrator để tạo lịch tắt/khởi động lại máy.)")
        elif show_success:
            messagebox.showinfo("Thành công", "Đã lưu cấu hình và áp dụng thành công.")
        return not errors

    def _check_license(self):
        key = self.var_license_key.get().strip()
        if not key:
            self.var_license_status.set("⚠ Chưa nhập License Key")
            self.lbl_license_status.configure(foreground="#a05a00")
            return

        self.var_license_status.set("Đang kiểm tra...")
        self.lbl_license_status.configure(foreground="#666666")
        self.update_idletasks()

        temp_cfg = dict(self.cfg)
        temp_cfg["license_key"] = key

        def worker():
            is_valid, message = license_manager.validate_license(temp_cfg)
            self.after(0, lambda: self._on_license_result(is_valid, message))

        threading.Thread(target=worker, daemon=True).start()

    def _on_license_result(self, is_valid: bool, message: str):
        prefix = "✅" if is_valid else "❌"
        self.var_license_status.set(f"{prefix} {message}")
        self.lbl_license_status.configure(foreground="#0a7d2c" if is_valid else "#c0392b")

    def _set_sync_busy(self, busy):
        state = "disabled" if busy else "normal"
        self.btn_sync.configure(state=state)
        self.btn_sync_play.configure(state=state)
        if busy:
            self.sync_progress.configure(mode="determinate", value=0)

    def _sync_worker(self, play_after=False):
        try:
            def progress(info):
                total = max(1, info.get("total", 1))
                value = info.get("index", 0) * 100 / total
                text = f"Đang xử lý {info.get('index', 0)}/{total}: {info.get('file', '')}"
                self.after(0, lambda: (
                    self.sync_progress.configure(value=value),
                    self.var_sync_status.set(text),
                ))

            result = sync_source_to_play(
                self.cfg["source_folder"], self.cfg["play_folder"], self.cfg,
                progress_callback=progress,
            )
            self.after(0, lambda: self._sync_done(result, play_after))
        except Exception as exc:
            self.after(0, lambda: self._sync_failed(str(exc)))

    def _start_sync(self, play_after=False):
        if not self._save(show_success=False):
            return
        try:
            validate_folder_layout(self.cfg["source_folder"], self.cfg["play_folder"])
        except Exception as exc:
            messagebox.showerror("Cấu hình thư mục không hợp lệ", str(exc))
            return
        self._set_sync_busy(True)
        self.var_sync_status.set("Đang chuẩn bị đồng bộ...")
        threading.Thread(target=self._sync_worker, args=(play_after,), daemon=True).start()

    def _sync_done(self, result, play_after):
        self._set_sync_busy(False)
        self.sync_progress.configure(value=100)
        self.var_sync_status.set(
            f"Hoàn tất: nguồn {result.total_source}, copy {result.copied}, "
            f"convert {result.converted}, không đổi {result.unchanged}, "
            f"lỗi {result.failed}, PLAY {result.play_file_count}."
        )
        if result.play_file_count == 0:
            messagebox.showerror("PLAY rỗng", "Không có ảnh/video hợp lệ để phát.")
            return
        if result.failed:
            messagebox.showwarning(
                "Đồng bộ có lỗi",
                "\n".join(result.errors[:10]) + "\n\nCác nội dung hợp lệ vẫn có thể phát.",
            )
        if play_after:
            subprocess.Popen(get_launcher_command() + ["--skip-sync"])

    def _sync_failed(self, message):
        self._set_sync_busy(False)
        self.var_sync_status.set("Đồng bộ thất bại.")
        messagebox.showerror("Lỗi đồng bộ", message)

    def _sync_now(self):
        self._start_sync(play_after=False)

    def _run_now(self):
        self._start_sync(play_after=True)

    def _play_only(self):
        if not self._save(show_success=False):
            return
        if not os.path.isdir(self.cfg["play_folder"]):
            messagebox.showerror("Lỗi", "Thư mục PLAY chưa tồn tại.")
            return
        try:
            subprocess.Popen(get_launcher_command() + ["--skip-sync"])
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể khởi động launcher: {e}")

    def _stop_vlc(self):
        if IS_WINDOWS:
            subprocess.run(
                ["taskkill", "/IM", "vlc.exe", "/F"],
                capture_output=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        self.var_sync_status.set("Đã gửi lệnh dừng VLC.")


if __name__ == "__main__":
    app = SettingsApp()
    app.mainloop()
