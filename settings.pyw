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
        self.title("Cấu hình ATG Multi Mornitor Control V1.0 — https://annguyen.pro")
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
        ttk.Label(frm, text="Thư mục media (video/ảnh):").grid(row=row, column=0, sticky="w", **pad)
        self.var_folder = tk.StringVar()
        ttk.Entry(frm, textvariable=self.var_folder, width=45).grid(row=row, column=1, **pad)
        ttk.Button(frm, text="Chọn...", command=self._browse_folder).grid(row=row, column=2, **pad)

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
        ttk.Button(btn_frame, text="Chạy thử VLC ngay", command=self._run_now).pack(side="left", padx=5)
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
        self.var_folder.set(c.get("media_folder", ""))
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

    def _browse_folder(self):
        path = filedialog.askdirectory(title="Chọn thư mục chứa video/ảnh")
        if path:
            self.var_folder.set(os.path.normpath(path))

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

    def _save(self):
        if self.var_shutdown_enabled.get() and not self._validate_time(self.var_shutdown_time.get()):
            messagebox.showerror("Lỗi", "Giờ tắt máy không hợp lệ. Định dạng đúng: HH:MM")
            return
        if self.var_restart_enabled.get() and not self._validate_time(self.var_restart_time.get()):
            messagebox.showerror("Lỗi", "Giờ khởi động lại không hợp lệ. Định dạng đúng: HH:MM")
            return
        if not os.path.exists(self.var_vlc.get()):
            if not messagebox.askyesno("Cảnh báo", "Không tìm thấy vlc.exe tại đường dẫn đã chọn. Vẫn tiếp tục lưu?"):
                return

        self.cfg.update({
            "vlc_path": os.path.normpath(self.var_vlc.get()),
            "media_folder": os.path.normpath(self.var_folder.get()),
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
        else:
            messagebox.showinfo("Thành công", "Đã lưu cấu hình và áp dụng thành công.")

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

    def _run_now(self):
        self._save()
        try:
            subprocess.Popen(get_launcher_command())
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể khởi động launcher: {e}")


if __name__ == "__main__":
    app = SettingsApp()
    app.mainloop()
