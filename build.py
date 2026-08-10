# -*- coding: utf-8 -*-
"""Build một file ATG-Multi-Mornitor-Control.exe chứa Settings, Launcher và assets."""
import os
import shutil
import subprocess
import sys

from common import APP_NAME

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DIST_RELEASE = os.path.join(APP_DIR, "dist_release")
PYINSTALLER_DIST = os.path.join(APP_DIR, "dist")
PYINSTALLER_WORK = os.path.join(APP_DIR, "build")
ENTRY_POINT = os.path.join(APP_DIR, f"{APP_NAME}.pyw")
ICON_PATH = os.path.join(APP_DIR, "assets", "app_icon.ico")
ASSETS_PATH = os.path.join(APP_DIR, "assets")
EXE_NAME = APP_NAME


def run(command):
    print(">>>", subprocess.list2cmdline(command))
    result = subprocess.run(command, cwd=APP_DIR)
    if result.returncode:
        raise SystemExit(result.returncode)


def main():
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("[LOI] Chua cai PyInstaller. Hay chay build.bat.")
        raise SystemExit(1)

    if not os.path.isfile(ENTRY_POINT):
        print(f"[LOI] Khong tim thay entry point: {ENTRY_POINT}")
        raise SystemExit(1)

    command = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--windowed",
        "--noconfirm",
        "--clean",
        "--name", EXE_NAME,
        "--distpath", PYINSTALLER_DIST,
        "--workpath", PYINSTALLER_WORK,
        "--specpath", PYINSTALLER_WORK,
        "--hidden-import", "settings",
        "--hidden-import", "launcher",
        "--hidden-import", "sync_engine",
        "--hidden-import", "fitz",
    ]
    if os.path.isfile(ICON_PATH):
        command.extend(["--icon", ICON_PATH])
    if os.path.isdir(ASSETS_PATH):
        command.extend(["--add-data", f"{ASSETS_PATH}{os.pathsep}assets"])
    command.append(ENTRY_POINT)

    print(f"== Build {APP_NAME}: 1 file EXE ==")
    run(command)

    # Chỉ xóa thư mục đầu ra do script này quản lý.
    if os.path.isdir(DIST_RELEASE):
        shutil.rmtree(DIST_RELEASE)
    os.makedirs(DIST_RELEASE)
    source_exe = os.path.join(PYINSTALLER_DIST, EXE_NAME + ".exe")
    target_exe = os.path.join(DIST_RELEASE, EXE_NAME + ".exe")
    shutil.copy2(source_exe, target_exe)

    print()
    print("=" * 60)
    print("BUILD THANH CONG")
    print(f"File phat hanh duy nhat: {target_exe}")
    print(f"Mo {EXE_NAME}.exe de cau hinh.")
    print(f"Che do khoi dong/VLC se tu goi: {EXE_NAME}.exe --launcher")
    print("=" * 60)


if __name__ == "__main__":
    main()
