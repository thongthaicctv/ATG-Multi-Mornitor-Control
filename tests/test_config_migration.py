# -*- coding: utf-8 -*-
from pathlib import Path
import tempfile
import unittest

import common
from secure_storage import save_encrypted_json


class ConfigMigrationTests(unittest.TestCase):
    def test_old_media_folder_is_migrated(self):
        with tempfile.TemporaryDirectory() as td:
            old_config = common.CONFIG_PATH
            old_legacy = common.LEGACY_CONFIG_PATH
            try:
                common.CONFIG_PATH = str(Path(td) / "config.atg")
                common.LEGACY_CONFIG_PATH = str(Path(td) / "config.json")
                save_encrypted_json(
                    common.CONFIG_PATH,
                    {"media_folder": r"D:\MEDIA", "license_key": "KEEP"},
                    "config",
                )
                cfg = common.load_config()
                self.assertEqual(cfg["source_folder"], r"D:\MEDIA")
                self.assertEqual(cfg["play_folder"], r"D:\MEDIA_PLAY")
                self.assertEqual(cfg["license_key"], "KEEP")
                self.assertIn("pdf_dpi", cfg)
            finally:
                common.CONFIG_PATH = old_config
                common.LEGACY_CONFIG_PATH = old_legacy

    def test_crop_fill_is_migrated_to_content_preserving_mode(self):
        with tempfile.TemporaryDirectory() as td:
            old_config, old_legacy = common.CONFIG_PATH, common.LEGACY_CONFIG_PATH
            try:
                common.CONFIG_PATH = str(Path(td) / "config.atg")
                common.LEGACY_CONFIG_PATH = str(Path(td) / "config.json")
                save_encrypted_json(common.CONFIG_PATH, {"image_display_mode": "crop_fill"}, "config")
                cfg = common.load_config()
                self.assertEqual(cfg["image_display_mode"], "fit_background")
            finally:
                common.CONFIG_PATH, common.LEGACY_CONFIG_PATH = old_config, old_legacy


if __name__ == "__main__":
    unittest.main()
