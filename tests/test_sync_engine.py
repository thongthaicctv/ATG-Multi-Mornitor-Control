# -*- coding: utf-8 -*-
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest import mock

import fitz
from PIL import Image

from common import build_playlist_file, scan_media_files
from sync_engine import (
    MANIFEST_NAME, SyncError, scan_source_files, sync_source_to_play,
    validate_folder_layout, process_image_for_play, find_libreoffice_executable,
)


class SyncEngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.source = root / "SOURCE"
        self.play = root / "PLAY"
        self.source.mkdir()
        self.cfg = {
            "recursive_scan": True,
            "remove_deleted_from_play": True,
            "pdf_dpi": 72,
            "libreoffice_path": "",
            "image_display_mode": "original",
            "crop_target_width": 1920,
            "crop_target_height": 1080,
            "normalize_image_orientation": False,
        }

    def tearDown(self):
        self.tmp.cleanup()

    def test_unsafe_layouts_are_blocked(self):
        with self.assertRaises(SyncError):
            validate_folder_layout(str(self.source), str(self.source))
        with self.assertRaises(SyncError):
            validate_folder_layout(str(self.source), str(self.source / "PLAY"))
        with self.assertRaises(SyncError):
            validate_folder_layout(str(self.play / "SOURCE"), str(self.play))

    def test_copy_media_unchanged_update_and_delete(self):
        image = self.source / "ảnh 01.png"
        image.write_bytes(b"one")
        first = sync_source_to_play(self.source, self.play, self.cfg)
        self.assertEqual(first.copied, 1)
        self.assertEqual((self.play / image.name).read_bytes(), b"one")
        second = sync_source_to_play(self.source, self.play, self.cfg)
        self.assertEqual(second.unchanged, 1)
        time.sleep(0.01)
        image.write_bytes(b"updated")
        third = sync_source_to_play(self.source, self.play, self.cfg)
        self.assertEqual(third.copied, 1)
        foreign = self.play / "nguoi_dung_tu_tao.txt"
        foreign.write_text("keep", encoding="utf-8")
        image.unlink()
        fourth = sync_source_to_play(self.source, self.play, self.cfg)
        self.assertGreaterEqual(fourth.deleted, 1)
        self.assertTrue(foreign.exists())

    def test_pdf_three_pages_to_png_with_vietnamese_name(self):
        pdf = self.source / "Thông báo.pdf"
        doc = fitz.open()
        for number in range(3):
            page = doc.new_page()
            page.insert_text((72, 72), f"Page {number + 1}")
        doc.save(pdf)
        doc.close()
        result = sync_source_to_play(self.source, self.play, self.cfg)
        self.assertEqual(result.converted, 1)
        pages = list((self.play / "Thông báo__pages").glob("*.png"))
        self.assertEqual(len(pages), 3)
        self.assertTrue(all(p.stat().st_size > 0 for p in pages))

        old_names = {p.name for p in pages}
        pdf.write_bytes(b"not-a-valid-pdf")
        failed = sync_source_to_play(self.source, self.play, self.cfg)
        self.assertEqual(failed.failed, 1)
        self.assertEqual({p.name for p in (self.play / "Thông báo__pages").glob("*.png")}, old_names)

    def test_office_temp_and_unsafe_files_ignored(self):
        (self.source / "~$file.docx").write_bytes(b"x")
        (self.source / "bad.exe").write_bytes(b"x")
        self.assertEqual(scan_source_files(self.source), [])

    def test_playlist_recursive_media_only_and_uri(self):
        nested = self.play / "Tầng 1"
        nested.mkdir(parents=True)
        (nested / "10.png").write_bytes(b"x")
        (nested / "2.png").write_bytes(b"x")
        (nested / "document.pdf").write_bytes(b"x")
        playlist = Path(self.tmp.name) / "playlist.m3u"
        files = build_playlist_file(self.play, str(playlist), recursive=True)
        self.assertEqual([Path(p).name for p in files], ["2.png", "10.png"])
        text = playlist.read_text(encoding="utf-8")
        self.assertIn("file:///", text)
        self.assertNotIn("document.pdf", text)

    def test_manifest_contains_only_managed_outputs(self):
        (self.source / "video.mp4").write_bytes(b"video")
        sync_source_to_play(self.source, self.play, self.cfg)
        data = json.loads((self.play / MANIFEST_NAME).read_text(encoding="utf-8"))
        self.assertIn("video.mp4", data["files"])
        self.assertEqual(data["files"]["video.mp4"]["outputs"], ["video.mp4"])

    def test_fit_background_preserves_complete_720x537_image(self):
        source = self.source / "notice.png"
        image = Image.new("RGB", (720, 537), "white")
        # Dấu màu sát bốn mép giúp xác nhận foreground không bị crop.
        for x in range(720):
            image.putpixel((x, 0), (255, 0, 0)); image.putpixel((x, 536), (0, 255, 0))
        for y in range(537):
            image.putpixel((0, y), (0, 0, 255)); image.putpixel((719, y), (255, 255, 0))
        image.save(source)
        cfg = dict(self.cfg, image_display_mode="fit_background", crop_target_width=1920,
                   crop_target_height=1080, trim_true_black_border=False)
        metadata = process_image_for_play(source, self.play / "fit.png", cfg)
        self.assertFalse(metadata["foreground_cropped"])
        self.assertTrue(metadata["content_preserved"])
        self.assertEqual((metadata["foreground_width"], metadata["foreground_height"]), (1448, 1080))
        self.assertEqual((metadata["foreground_x"], metadata["foreground_y"]), (236, 0))
        self.assertEqual(metadata["background_style"], "blur")
        with Image.open(self.play / "fit.png") as output:
            self.assertEqual(output.size, (1920, 1080))

    def test_document_page_uses_solid_background_and_no_crop(self):
        source = self.source / "page.png"
        Image.new("RGB", (1200, 1800), "white").save(source)
        cfg = dict(self.cfg, image_display_mode="fit_background", crop_target_width=1920,
                   crop_target_height=1080, trim_true_black_border=False)
        metadata = process_image_for_play(source, self.play / "page-fit.png", cfg, source_kind="pdf_page")
        self.assertEqual((metadata["foreground_width"], metadata["foreground_height"]), (720, 1080))
        self.assertEqual((metadata["foreground_x"], metadata["foreground_y"]), (600, 0))
        self.assertEqual(metadata["background_style"], "solid")
        self.assertTrue(metadata["content_preserved"])

    def test_config_change_forces_image_reprocessing_and_video_is_unchanged(self):
        image = self.source / "poster.png"
        video = self.source / "clip.mp4"
        Image.new("RGB", (50, 90), "orange").save(image)
        video.write_bytes(b"video-content")
        cfg = dict(self.cfg, normalize_image_orientation=True)
        first = sync_source_to_play(self.source, self.play, cfg)
        self.assertEqual(first.copied, 2)
        data = json.loads((self.play / MANIFEST_NAME).read_text(encoding="utf-8"))
        output = self.play / data["files"]["poster.png"]["outputs"][0]
        with Image.open(output) as opened:
            self.assertEqual(opened.size, (50, 90))
        cfg["image_display_mode"] = "fit_background"
        cfg["crop_target_width"] = 90
        cfg["crop_target_height"] = 50
        second = sync_source_to_play(self.source, self.play, cfg)
        self.assertEqual(second.copied, 1)
        self.assertEqual(second.unchanged, 1)
        with Image.open(output) as opened:
            self.assertEqual(opened.size, (90, 50))
        self.assertEqual((self.play / "clip.mp4").read_bytes(), b"video-content")

    def test_find_libreoffice_accepts_only_nonempty_soffice(self):
        fake = Path(self.tmp.name) / "soffice.exe"
        fake.write_bytes(b"exe")
        self.assertEqual(find_libreoffice_executable(str(fake)), fake.resolve())
        wrong = Path(self.tmp.name) / "wpsoffice.exe"
        wrong.write_bytes(b"exe")
        with mock.patch.dict("os.environ", {"PROGRAMFILES": str(Path(self.tmp.name) / "none")}, clear=False):
            selected = find_libreoffice_executable(str(wrong))
            self.assertNotEqual(selected, wrong.resolve())
            if selected:
                self.assertEqual(selected.name.casefold(), "soffice.exe")


if __name__ == "__main__":
    unittest.main()
