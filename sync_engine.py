# -*- coding: utf-8 -*-
"""Đồng bộ SOURCE -> PLAY và chuyển tài liệu thành ảnh để VLC phát."""
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import json
import os
import shutil
import subprocess
import tempfile
import time
import uuid

from common import (
    APP_NAME, APP_DIR, IMAGE_EXT, VIDEO_EXT, PDF_EXT, OFFICE_EXT, resource_log
)

MANIFEST_NAME = ".atg_sync_manifest.json"
MARKER_NAME = ".play_folder_managed.json"
CONVERSION_VERSION = "phase-1.2.4-fit-background-v5"


class SyncError(RuntimeError):
    pass


@dataclass
class SyncResult:
    total_source: int = 0
    copied: int = 0
    converted: int = 0
    unchanged: int = 0
    deleted: int = 0
    failed: int = 0
    play_file_count: int = 0
    errors: list = field(default_factory=list)
    started_at: str = ""
    finished_at: str = ""


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _atomic_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".tmp-{uuid.uuid4().hex}")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def validate_folder_layout(source_folder: str, play_folder: str):
    if not source_folder or not play_folder:
        raise SyncError("Thư mục SOURCE và PLAY không được để trống.")
    source = Path(source_folder).expanduser().resolve()
    play = Path(play_folder).expanduser().resolve()
    if source == play:
        raise SyncError("SOURCE và PLAY không được trùng nhau.")
    if source in play.parents:
        raise SyncError("PLAY không được nằm bên trong SOURCE.")
    if play in source.parents:
        raise SyncError("SOURCE không được nằm bên trong PLAY.")
    if source == Path(source.anchor) or play == Path(play.anchor):
        raise SyncError("Không được chọn thư mục gốc ổ đĩa làm SOURCE hoặc PLAY.")
    app = Path(APP_DIR).resolve()
    if play == app or play in app.parents or app in play.parents:
        raise SyncError("PLAY không được trỏ vào thư mục ứng dụng hoặc thư mục cha của ứng dụng.")
    return source, play


def scan_source_files(source_folder: str, recursive=True):
    source = Path(source_folder)
    allowed = IMAGE_EXT | VIDEO_EXT | PDF_EXT | OFFICE_EXT
    iterator = source.rglob("*") if recursive else source.glob("*")
    result = []
    for path in iterator:
        if not path.is_file() or path.name.startswith("~$"):
            continue
        if path.name in (MANIFEST_NAME, MARKER_NAME, "config.atg", "license_cache.atg", "playlist.m3u"):
            continue
        if ".atg_tmp_" in path.name or path.suffix.lower() not in allowed:
            continue
        result.append(path)
    return sorted(result, key=lambda p: _natural_key(str(p.relative_to(source))))


def _natural_key(value):
    import re
    return [int(part) if part.isdigit() else part.casefold() for part in re.split(r"(\d+)", value)]


def load_manifest(play_folder: str):
    path = Path(play_folder) / MANIFEST_NAME
    if not path.exists():
        return {"version": 1, "files": {}}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data.get("files"), dict):
            raise ValueError
        return data
    except Exception:
        resource_log("[SYNC] Manifest lỗi; dùng manifest rỗng và không xóa file cũ.")
        return {"version": 1, "files": {}}


def save_manifest(play_folder: str, manifest: dict):
    _atomic_json(Path(play_folder) / MANIFEST_NAME, manifest)


def _ensure_marker(source: Path, play: Path):
    marker = play / MARKER_NAME
    if not marker.exists():
        _atomic_json(marker, {
            "app": APP_NAME,
            "version": "1.2",
            "source_folder": str(source),
            "play_folder_id": uuid.uuid4().hex,
            "created_at": _now(),
        })


def copy_media_atomic(source: Path, target: Path):
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name(target.name + f".atg_tmp_{uuid.uuid4().hex}")
    try:
        shutil.copy2(source, temp)
        if temp.stat().st_size != source.stat().st_size:
            raise SyncError(f"Kích thước copy không khớp: {source}")
        os.replace(temp, target)
    finally:
        if temp.exists():
            temp.unlink(missing_ok=True)


def _image_settings(config: dict):
    mode = config.get("image_display_mode", "fit_background")
    if mode == "crop_fill":
        mode = "fit_background"
    if mode not in {"original", "fit_background", "stretch_fill"}:
        mode = "fit_background"
    width = max(1, int(config.get("crop_target_width", 1920)))
    height = max(1, int(config.get("crop_target_height", 1080)))
    return mode, width, height, bool(config.get("normalize_image_orientation", True))


def _orientation_version(config: dict):
    mode, width, height, normalize = _image_settings(config)
    fmt = str(config.get("processed_image_format", "png")).lower()
    quality = int(config.get("jpeg_output_quality", 95))
    style = config.get("fit_background_style", "auto")
    photo = config.get("photo_background_style", "blur")
    document = config.get("document_background_style", "solid")
    color = str(config.get("document_background_color", "#FFFFFF")).replace("#", "")
    blur = config.get("background_blur_radius", 28)
    brightness = config.get("background_brightness", 0.60)
    saturation = config.get("background_saturation", 0.75)
    return (f"{CONVERSION_VERSION}-{mode}-{width}x{height}-{style}-{photo}-{document}-{color}-"
            f"blur{blur}-b{brightness}-s{saturation}-exif{int(normalize)}-{fmt}-q{quality}")


def _save_image_atomic(image, output_image: Path, config: dict):
    from PIL import Image
    fmt = str(config.get("processed_image_format", "png")).lower()
    fmt = "jpeg" if fmt in {"jpg", "jpeg"} else "png"
    if fmt == "jpeg" and image.mode != "RGB":
        image = image.convert("RGB")
    output_image.parent.mkdir(parents=True, exist_ok=True)
    temp = output_image.with_name(output_image.name + f".atg_tmp_{uuid.uuid4().hex}")
    try:
        save_args = {"format": fmt.upper()}
        if fmt == "jpeg":
            save_args.update(quality=int(config.get("jpeg_output_quality", 95)), optimize=True)
        image.save(temp, **save_args)
        with Image.open(temp) as check:
            check.verify()
        os.replace(temp, output_image)
    finally:
        temp.unlink(missing_ok=True)
    return fmt


def _trim_true_black_border(image, config):
    if not config.get("trim_true_black_border", True):
        return image, [0, 0, image.width, image.height]
    threshold = int(config.get("black_border_threshold", 10))
    ratio = float(config.get("black_border_required_ratio", 0.995))
    max_percent = min(0.08, float(config.get("black_border_max_percent", 0.08)))
    gray = image.convert("L")
    width, height = gray.size
    max_x, max_y = int(width * max_percent), int(height * max_percent)

    def dark_enough(box, count):
        histogram = gray.crop(box).histogram()
        return sum(histogram[:threshold + 1]) / max(1, count) >= ratio

    left = 0
    while left < max_x and dark_enough((left, 0, left + 1, height), height): left += 1
    right = width
    while width - right < max_x and dark_enough((right - 1, 0, right, height), height): right -= 1
    top = 0
    while top < max_y and dark_enough((left, top, right, top + 1), max(1, right - left)): top += 1
    bottom = height
    while height - bottom < max_y and dark_enough((left, bottom - 1, right, bottom), max(1, right - left)): bottom -= 1
    box = [left, top, right, bottom]
    if box != [0, 0, width, height] and right > left and bottom > top:
        resource_log(f"[SYNC] TRUE BLACK BORDER TRIMMED box={box} source={width}x{height}")
        return image.crop(tuple(box)), box
    return image, box


def render_fit_background(source_image: Path, output_image: Path, target_width: int,
                          target_height: int, source_kind: str, config: dict) -> dict:
    from PIL import Image, ImageOps, ImageFilter, ImageEnhance
    with Image.open(source_image) as opened:
        orientation = opened.getexif().get(274, 1)
        foreground = ImageOps.exif_transpose(opened)
        foreground.load()
        foreground = foreground.convert("RGBA")
        source_width, source_height = foreground.size
        foreground, trim_box = _trim_true_black_border(foreground, config)

    is_document = source_kind != "image"
    style_setting = config.get("fit_background_style", "auto")
    if style_setting == "auto":
        style = config.get("document_background_style", "solid") if is_document else config.get("photo_background_style", "blur")
    else:
        style = style_setting
    if style not in {"blur", "solid"}:
        style = "solid" if is_document else "blur"

    resource_log(f"[SYNC] IMAGE DISPLAY MODE: fit_background | FOREGROUND CONTAIN START {source_image.name}")
    if style == "blur":
        base = foreground.convert("RGB")
        background = ImageOps.fit(base, (target_width, target_height), method=Image.Resampling.LANCZOS,
                                  centering=(0.5, 0.5))
        background = background.filter(ImageFilter.GaussianBlur(radius=float(config.get("background_blur_radius", 28))))
        background = ImageEnhance.Brightness(background).enhance(float(config.get("background_brightness", 0.60)))
        background = ImageEnhance.Color(background).enhance(float(config.get("background_saturation", 0.75)))
        resource_log(f"[SYNC] BACKGROUND BLUR CREATED {source_image.name}")
        background_cropped = foreground.size != (target_width, target_height)
    else:
        color = config.get("document_background_color", "#FFFFFF")
        background = Image.new("RGB", (target_width, target_height), color)
        resource_log(f"[SYNC] DOCUMENT SOLID BACKGROUND CREATED {source_image.name} color={color}")
        background_cropped = False

    max_width = target_width * float(config.get("foreground_max_width_percent", 1.0))
    max_height = target_height * float(config.get("foreground_max_height_percent", 1.0))
    scale = min(max_width / foreground.width, max_height / foreground.height)
    foreground_width = max(1, min(target_width, round(foreground.width * scale)))
    foreground_height = max(1, min(target_height, round(foreground.height * scale)))
    resized = foreground.resize((foreground_width, foreground_height), Image.Resampling.LANCZOS)
    x = (target_width - foreground_width) // 2
    y = (target_height - foreground_height) // 2
    background.paste(resized, (x, y), resized)
    fmt = _save_image_atomic(background, output_image, config)
    metadata = {
        "display_mode": "fit_background", "source_kind": source_kind,
        "source_width": source_width, "source_height": source_height,
        "target_width": target_width, "target_height": target_height,
        "foreground_width": foreground_width, "foreground_height": foreground_height,
        "foreground_x": x, "foreground_y": y, "foreground_cropped": False,
        "content_preserved": True, "background_style": style,
        "background_cropped": background_cropped, "output_width": target_width,
        "output_height": target_height, "trim_box": trim_box,
        "exif_transposed": orientation not in (None, 1), "rotated": False,
        "output_format": fmt,
    }
    resource_log(f"[SYNC] FOREGROUND CONTAIN SUCCESS | source={source_image.name} | "
                 f"source_size={source_width}x{source_height} | target={target_width}x{target_height} | "
                 f"foreground={foreground_width}x{foreground_height} | position={x},{y} | "
                 "cropped=false | content_preserved=true")
    return metadata


def process_image_for_play(source_image: Path, output_image: Path, config: dict, source_kind="image") -> dict:
    """Tạo ảnh PLAY theo original, fit-background hoặc stretch; không xoay nội dung."""
    from PIL import Image, ImageOps
    mode, target_width, target_height, normalize = _image_settings(config)
    if mode == "fit_background":
        return render_fit_background(source_image, output_image, target_width, target_height, source_kind, config)

    with Image.open(source_image) as opened:
        orientation = opened.getexif().get(274, 1)
        image = ImageOps.exif_transpose(opened) if normalize else opened.copy()
        image.load()
        original_width, original_height = image.size
        if mode == "stretch_fill":
            image = image.resize((target_width, target_height), Image.Resampling.LANCZOS)
        detached = image.copy()
    fmt = _save_image_atomic(detached, output_image, config)

    metadata = {
        "original_width": original_width, "original_height": original_height,
        "output_width": detached.width, "output_height": detached.height,
        "exif_transposed": bool(normalize and orientation not in (None, 1)),
        "foreground_cropped": False, "content_preserved": True,
        "rotated": False, "rotation_degrees": 0, "display_mode": mode, "output_format": fmt,
    }
    return metadata


def convert_pdf_to_images(pdf_path: Path, output_dir: Path, dpi=150):
    try:
        import fitz
    except ImportError as exc:
        raise SyncError("Chưa cài PyMuPDF để chuyển PDF thành ảnh.") from exc
    resource_log(f"[SYNC] PDF RENDER START {pdf_path}")
    output_dir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(str(pdf_path))
    try:
        if doc.page_count < 1:
            raise SyncError(f"PDF không có trang: {pdf_path.name}")
        scale = float(dpi) / 72.0
        matrix = fitz.Matrix(scale, scale)
        outputs = []
        stem = pdf_path.stem
        for index, page in enumerate(doc, 1):
            target = output_dir / f"{stem}__page_{index:04d}.png"
            page.get_pixmap(matrix=matrix, alpha=False).save(str(target))
            if not target.exists() or target.stat().st_size == 0:
                raise SyncError(f"Không tạo được ảnh trang {index}: {pdf_path.name}")
            outputs.append(target)
        resource_log(f"[SYNC] PDF RENDER SUCCESS {pdf_path.name} pages={len(outputs)}")
        return outputs
    finally:
        doc.close()


def _valid_soffice(path) -> bool:
    try:
        candidate = Path(path)
        return (candidate.name.casefold() == "soffice.exe" and candidate.is_file()
                and candidate.stat().st_size > 0 and os.access(candidate, os.R_OK))
    except (OSError, TypeError):
        return False


def find_libreoffice_executable(configured_path=None):
    resource_log("[SYNC] LIBREOFFICE SEARCH START")
    candidates = [configured_path,
                  r"C:\Program Files\LibreOffice\program\soffice.exe",
                  r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"]
    for variable in ("PROGRAMFILES", "PROGRAMFILES(X86)"):
        root = os.environ.get(variable)
        if root:
            candidates.append(str(Path(root) / "LibreOffice" / "program" / "soffice.exe"))
    seen = set()
    for value in candidates:
        if not value or str(value).casefold() in seen:
            continue
        seen.add(str(value).casefold())
        resource_log(f"[SYNC] LIBREOFFICE CANDIDATE {value}")
        if _valid_soffice(value):
            selected = Path(value).resolve()
            resource_log(f"[SYNC] LIBREOFFICE SELECTED {selected}")
            return selected
    return None


def _windows_process_options():
    if os.name != "nt":
        return {}
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    return {"startupinfo": startup, "creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)}


def _windows_file_version(path: Path):
    if os.name != "nt":
        return ""
    try:
        import ctypes
        from ctypes import wintypes
        size = ctypes.windll.version.GetFileVersionInfoSizeW(str(path), None)
        if not size:
            return ""
        buffer = ctypes.create_string_buffer(size)
        if not ctypes.windll.version.GetFileVersionInfoW(str(path), 0, size, buffer):
            return ""
        pointer, length = ctypes.c_void_p(), wintypes.UINT()
        if not ctypes.windll.version.VerQueryValueW(buffer, "\\", ctypes.byref(pointer), ctypes.byref(length)):
            return ""
        values = ctypes.cast(pointer, ctypes.POINTER(wintypes.DWORD * 13)).contents
        ms, ls = values[2], values[3]
        return f"{ms >> 16}.{ms & 0xffff}.{ls >> 16}.{ls & 0xffff}"
    except Exception:
        return ""


class LibreOfficeConverter:
    def __init__(self, soffice_path: Path, timeout_seconds: int = 180):
        self.soffice_path = Path(soffice_path)
        self.timeout_seconds = max(15, int(timeout_seconds))
        self.version = "unknown"

    def validate(self):
        if not _valid_soffice(self.soffice_path):
            return False, "Đường dẫn LibreOffice không hợp lệ. Hãy chọn soffice.exe."
        try:
            with tempfile.TemporaryDirectory(prefix="atg-lo-check-") as profile_dir:
                profile_uri = Path(profile_dir).resolve().as_uri()
                stdout_path = Path(profile_dir) / "stdout.txt"
                stderr_path = Path(profile_dir) / "stderr.txt"
                with open(stdout_path, "w", encoding="utf-8", errors="replace") as stdout_file, \
                     open(stderr_path, "w", encoding="utf-8", errors="replace") as stderr_file:
                    result = subprocess.run([str(self.soffice_path), f"-env:UserInstallation={profile_uri}",
                                             "--headless", "--version"], shell=False,
                                            stdout=stdout_file, stderr=stderr_file, text=True,
                                            timeout=15, **_windows_process_options())
                text = (stdout_path.read_text(encoding="utf-8", errors="replace") or
                        stderr_path.read_text(encoding="utf-8", errors="replace")).strip()[:500]
            if result.returncode != 0 or not text:
                return False, text or f"Mã lỗi {result.returncode}"
            self.version = text
            resource_log(f"[SYNC] LIBREOFFICE VERSION {text}")
            return True, text
        except subprocess.TimeoutExpired:
            version = _windows_file_version(self.soffice_path)
            if version:
                self.version = f"LibreOffice {version} (file version)"
                resource_log(f"[SYNC] LIBREOFFICE VERSION {self.version}; --version timeout")
                return True, self.version
            return False, "LibreOffice không phản hồi khi kiểm tra phiên bản."
        except Exception as exc:
            resource_log(f"[SYNC] LIBREOFFICE CONVERT FAILED validate: {exc}")
            return False, str(exc)

    def convert_to_pdf(self, source_file: Path, output_directory: Path) -> Path:
        import fitz
        output_directory.mkdir(parents=True, exist_ok=True)
        profile = output_directory / f"lo_profile_{uuid.uuid4().hex}"
        profile.mkdir()
        before = {p.resolve() for p in output_directory.glob("*.pdf")}
        command = [str(self.soffice_path), f"-env:UserInstallation={profile.resolve().as_uri()}",
                   "--headless", "--nologo", "--nodefault", "--nofirststartwizard", "--nolockcheck",
                   "--convert-to", "pdf", "--outdir", str(output_directory), str(source_file)]
        resource_log(f"[SYNC] LIBREOFFICE CONVERT START {source_file}")
        resource_log(f"[SYNC] LIBREOFFICE COMMAND {subprocess.list2cmdline(command)}")
        stdout_path = output_directory / f".lo-stdout-{uuid.uuid4().hex}.txt"
        stderr_path = output_directory / f".lo-stderr-{uuid.uuid4().hex}.txt"
        try:
            with open(stdout_path, "w", encoding="utf-8", errors="replace") as stdout_file, \
                 open(stderr_path, "w", encoding="utf-8", errors="replace") as stderr_file:
                result = subprocess.run(command, shell=False, stdout=stdout_file, stderr=stderr_file, text=True,
                                        timeout=self.timeout_seconds, **_windows_process_options())
        except subprocess.TimeoutExpired as exc:
            resource_log(f"[SYNC] LIBREOFFICE TIMEOUT {source_file.name}")
            raise SyncError(f"LibreOffice quá thời gian {self.timeout_seconds} giây: {source_file.name}") from exc
        stdout_text = stdout_path.read_text(encoding="utf-8", errors="replace") if stdout_path.exists() else ""
        stderr_text = stderr_path.read_text(encoding="utf-8", errors="replace") if stderr_path.exists() else ""
        stdout_path.unlink(missing_ok=True)
        stderr_path.unlink(missing_ok=True)
        if result.returncode != 0:
            detail = ((stderr_text or stdout_text or "")[:2000]).strip()
            resource_log(f"[SYNC] LIBREOFFICE CONVERT FAILED {source_file.name}: {detail}")
            raise SyncError(f"LibreOffice chuyển đổi thất bại: {source_file.name}: {detail}")
        created = [p for p in output_directory.glob("*.pdf") if p.resolve() not in before and p.stat().st_size > 0]
        preferred = [p for p in created if p.stem.casefold() == source_file.stem.casefold()]
        candidates = preferred or created
        if not candidates:
            raise SyncError(f"LibreOffice không tạo được PDF: {source_file.name}")
        pdf = max(candidates, key=lambda p: p.stat().st_mtime_ns)
        try:
            with fitz.open(str(pdf)) as document:
                if document.page_count < 1:
                    raise ValueError("PDF không có trang")
        except Exception as exc:
            raise SyncError(f"PDF LibreOffice tạo ra không hợp lệ: {pdf.name}") from exc
        resource_log(f"[SYNC] LIBREOFFICE PDF OUTPUT {pdf}")
        resource_log(f"[SYNC] LIBREOFFICE CONVERT SUCCESS {source_file.name}")
        return pdf


def get_libreoffice_converter(config: dict, validate=False):
    path = find_libreoffice_executable(config.get("libreoffice_path"))
    if not path:
        raise SyncError("Chưa tìm thấy LibreOffice. Hãy cài LibreOffice và chọn file soffice.exe trong Cài đặt.")
    converter = LibreOfficeConverter(path, config.get("libreoffice_timeout_seconds", 180))
    if validate:
        valid, message = converter.validate()
        if not valid:
            raise SyncError(f"LibreOffice không hợp lệ: {message}")
    return converter


def convert_office_to_pdf(source: Path, output_dir: Path, config: dict):
    return get_libreoffice_converter(config).convert_to_pdf(source, output_dir)


def convert_document_atomic(source: Path, final_dir: Path, config: dict):
    final_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".atg-stage-", dir=str(final_dir.parent)))
    backup = final_dir.with_name(final_dir.name + f".backup-{uuid.uuid4().hex}")
    try:
        if source.suffix.lower() == ".pdf":
            pdf = source
        else:
            pdf = convert_office_to_pdf(source, staging, config)
        image_stage = staging / "pages"
        outputs = convert_pdf_to_images(pdf, image_stage, int(config.get("pdf_dpi", 150)))
        metadata = []
        if source.suffix.lower() == ".pdf":
            page_kind = "pdf_page"
        elif source.suffix.lower() in {".doc", ".docx", ".rtf", ".odt"}:
            page_kind = "word_page"
        elif source.suffix.lower() in {".xls", ".xlsx", ".xlsm", ".ods"}:
            page_kind = "excel_page"
        else:
            page_kind = "powerpoint_page"
        for output in outputs:
            item = process_image_for_play(output, output, config, source_kind=page_kind)
            item["file_name"] = output.name
            metadata.append(item)
        if final_dir.exists():
            os.replace(final_dir, backup)
        os.replace(image_stage, final_dir)
        shutil.rmtree(backup, ignore_errors=True)
        resource_log(f"[SYNC] DOCUMENT OUTPUT REPLACED {final_dir}")
        return [final_dir / path.name for path in outputs], metadata
    except Exception:
        if not final_dir.exists() and backup.exists():
            os.replace(backup, final_dir)
        raise
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def remove_deleted_outputs(source_rel: str, entry: dict, play: Path):
    deleted = 0
    for rel in entry.get("outputs", []):
        target = (play / rel).resolve()
        if play not in target.parents:
            continue
        if target.is_file():
            target.unlink()
            deleted += 1
    for rel in sorted(entry.get("outputs", []), key=len, reverse=True):
        parent = (play / rel).parent
        while parent != play and parent.exists():
            try:
                parent.rmdir()
            except OSError:
                break
            parent = parent.parent
    return deleted


def sync_source_to_play(source_folder, play_folder, config, progress_callback=None, cancel_event=None):
    started = time.monotonic()
    result = SyncResult(started_at=_now())
    source, play = validate_folder_layout(source_folder, play_folder)
    if not source.is_dir():
        raise SyncError(f"Thư mục SOURCE không tồn tại: {source}")
    play.mkdir(parents=True, exist_ok=True)
    _ensure_marker(source, play)
    manifest = load_manifest(str(play))
    old_files = manifest.get("files", {})
    new_files = dict(old_files)
    files = scan_source_files(str(source), bool(config.get("recursive_scan", True)))
    office_converter = None
    office_version = "not-required"
    if any(path.suffix.lower() in OFFICE_EXT for path in files):
        try:
            office_converter = get_libreoffice_converter(config, validate=True)
            office_version = office_converter.version.replace(" ", "_")
            config["libreoffice_path"] = str(office_converter.soffice_path)
        except Exception as exc:
            office_version = "unavailable"
            resource_log(f"[SYNC] LIBREOFFICE CONVERT FAILED initialization: {exc}")
    result.total_source = len(files)
    resource_log(f"[SYNC] START SOURCE={source} PLAY={play} files={len(files)}")

    for index, path in enumerate(files, 1):
        if cancel_event is not None and cancel_event.is_set():
            raise SyncError("Đồng bộ đã bị hủy.")
        rel = path.relative_to(source)
        key = rel.as_posix()
        stat = path.stat()
        ext = path.suffix.lower()
        kind = "image" if ext in IMAGE_EXT else ("video" if ext in VIDEO_EXT else ("pdf" if ext == ".pdf" else "office"))
        conversion = "copy-v1" if kind == "video" else (
            f"{kind}-{office_version if kind == 'office' else 'pymupdf'}-{int(config.get('pdf_dpi',150))}dpi-{_orientation_version(config)}"
            if kind in {"pdf", "office"} else f"image-{_orientation_version(config)}"
        )
        previous = old_files.get(key, {})
        outputs_ok = all((play / p).is_file() for p in previous.get("outputs", []))
        unchanged = (
            previous.get("source_size") == stat.st_size
            and previous.get("source_mtime_ns") == stat.st_mtime_ns
            and previous.get("conversion_version") == conversion
            and previous.get("status") == "success"
            and outputs_ok
        )
        if progress_callback:
            progress_callback({"index": index, "total": len(files), "file": key})
        if unchanged:
            result.unchanged += 1
            continue
        try:
            output_metadata = []
            if kind == "video":
                target = play / rel
                copy_media_atomic(path, target)
                outputs = [target]
                result.copied += 1
            elif kind == "image":
                mode, _, _, normalize = _image_settings(config)
                if mode == "original" and not normalize:
                    target = play / rel
                    copy_media_atomic(path, target)
                    outputs = [target]
                else:
                    fmt = str(config.get("processed_image_format", "png")).lower()
                    suffix = ".jpg" if fmt in {"jpg", "jpeg"} else ".png"
                    target = play / rel.parent / f"{path.name}{suffix}"
                    output_metadata = [process_image_for_play(path, target, config)]
                    outputs = [target]
                result.copied += 1
            else:
                final_dir = play / rel.parent / f"{path.stem}__pages"
                outputs, output_metadata = convert_document_atomic(path, final_dir, config)
                result.converted += 1
            new_output_rel = [str(p.relative_to(play)).replace("/", "\\") for p in outputs]
            for old_output in previous.get("outputs", []):
                if old_output not in new_output_rel:
                    old_target = (play / old_output).resolve()
                    if play in old_target.parents and old_target.is_file():
                        old_target.unlink()
            new_files[key] = {
                "source_relative_path": key,
                "source_size": stat.st_size,
                "source_mtime_ns": stat.st_mtime_ns,
                "source_type": kind,
                "conversion_version": conversion,
                "outputs": new_output_rel,
                "image_display_mode": config.get("image_display_mode", "original"),
                "crop_target_width": int(config.get("crop_target_width", 1920)),
                "crop_target_height": int(config.get("crop_target_height", 1080)),
                "fit_background_style": config.get("fit_background_style", "auto"),
                "photo_background_style": config.get("photo_background_style", "blur"),
                "document_background_style": config.get("document_background_style", "solid"),
                "converter_type": "libreoffice" if kind == "office" else "native",
                "converter_path": str(office_converter.soffice_path) if kind == "office" and office_converter else "",
                "converter_version": office_converter.version if kind == "office" and office_converter else "",
                "output_metadata": output_metadata,
                "status": "success",
                "last_sync": _now(),
            }
        except Exception as exc:
            result.failed += 1
            result.errors.append(f"{key}: {exc}")
            resource_log(f"[SYNC] ERROR {key}: {exc}")
            if previous:
                new_files[key] = previous

    current_keys = {p.relative_to(source).as_posix() for p in files}
    if config.get("remove_deleted_from_play", True):
        for key in list(old_files):
            if key not in current_keys:
                result.deleted += remove_deleted_outputs(key, old_files[key], play)
                new_files.pop(key, None)
    manifest = {"version": 1, "updated_at": _now(), "source_folder": str(source), "files": new_files}
    save_manifest(str(play), manifest)
    from common import scan_media_files
    result.play_file_count = len(scan_media_files(str(play), recursive=True))
    result.finished_at = _now()
    resource_log(
        f"[SYNC] DONE copied={result.copied} converted={result.converted} "
        f"unchanged={result.unchanged} deleted={result.deleted} failed={result.failed} "
        f"play={result.play_file_count} elapsed={time.monotonic()-started:.1f}s"
    )
    return result
