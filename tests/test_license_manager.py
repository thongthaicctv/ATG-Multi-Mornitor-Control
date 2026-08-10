# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import license_manager as lm
from hardware_identity import get_machine_code
from secure_storage import load_encrypted_json, save_encrypted_json


class LicenseManagerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cache_path = str(Path(self.tmp.name) / "ProgramData" / "license_cache.atg")
        self.cache_patch = mock.patch.object(lm, "CACHE_PATH", self.cache_path)
        self.cache_patch.start()
        self.legacy_cache_path = str(Path(self.tmp.name) / "legacy" / "license_cache.atg")
        self.legacy_patch = mock.patch.object(lm, "LEGACY_CACHE_PATH", self.legacy_cache_path)
        self.legacy_patch.start()
        self.key = "ATG-TEST"
        self.machine = get_machine_code()

    def tearDown(self):
        self.cache_patch.stop()
        self.legacy_patch.stop()
        self.tmp.cleanup()

    def row(self, **changes):
        row = {
            "LicenseKey": self.key,
            "TenKhachHang": "Test Customer",
            "TrangThai": "active",
            "NgayHetHan": (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d"),
            "MaMay": self.machine,
            "ThoiGianOffline": "7",
        }
        row.update(changes)
        return row

    def validate_rows(self, rows):
        with mock.patch.object(lm, "_fetch_license_rows", return_value=rows):
            return lm.validate_license_detailed({"license_key": self.key})

    def write_cache(self, **changes):
        now = datetime.now()
        data = {
            "license_key": self.key,
            "machine_code": self.machine,
            "valid": True,
            "customer": "Test Customer",
            "license_expiry": (now + timedelta(days=30)).isoformat(timespec="seconds"),
            "offline_days": 7,
            "online_checked_at": (now - timedelta(days=1)).isoformat(timespec="seconds"),
            "last_seen_at": now.isoformat(timespec="seconds"),
            "message": "License hợp lệ — Online",
        }
        data.update(changes)
        save_encrypted_json(self.cache_path, data, "license-cache")
        return data

    def validate_offline(self):
        with mock.patch.object(lm, "_fetch_license_rows", return_value=None):
            return lm.validate_license_detailed({"license_key": self.key})

    def test_online_valid_license(self):
        result = self.validate_rows([self.row()])
        self.assertTrue(result.valid)
        self.assertEqual(result.source, "online")
        cache = load_encrypted_json(self.cache_path, "license-cache")
        self.assertEqual(cache["customer"], "Test Customer")
        self.assertIn("license_expiry", cache)

    def test_online_expired(self):
        result = self.validate_rows([self.row(NgayHetHan="2000-01-01")])
        self.assertEqual((result.valid, result.reason), (False, "expired"))

    def test_online_blocked(self):
        result = self.validate_rows([self.row(TrangThai="blocked")])
        self.assertEqual((result.valid, result.reason), (False, "blocked"))

    def test_online_wrong_machine(self):
        result = self.validate_rows([self.row(MaMay="OTHER")])
        self.assertEqual((result.valid, result.reason), (False, "wrong_machine"))

    def test_online_license_missing_does_not_fallback(self):
        self.write_cache()
        result = self.validate_rows([])
        self.assertEqual((result.valid, result.source, result.reason), (False, "online", "missing"))

    def test_offline_valid_cache(self):
        original = self.write_cache()
        result = self.validate_offline()
        self.assertEqual((result.valid, result.source), (True, "offline"))
        refreshed = load_encrypted_json(self.cache_path, "license-cache")
        self.assertEqual(refreshed["online_checked_at"], original["online_checked_at"])

    def test_offline_days_expired(self):
        old = (datetime.now() - timedelta(days=8)).isoformat(timespec="seconds")
        self.write_cache(online_checked_at=old, last_seen_at=old)
        result = self.validate_offline()
        self.assertEqual(result.reason, "offline_expired")

    def test_license_expiry_reached_offline(self):
        self.write_cache(license_expiry=(datetime.now() - timedelta(seconds=1)).isoformat(timespec="seconds"))
        result = self.validate_offline()
        self.assertEqual(result.reason, "expired")

    def test_offline_wrong_machine(self):
        self.write_cache(machine_code="OTHER")
        result = self.validate_offline()
        self.assertEqual(result.reason, "wrong_machine")

    def test_offline_corrupted_cache(self):
        Path(self.cache_path).parent.mkdir(parents=True)
        Path(self.cache_path).write_text("not encrypted", encoding="utf-8")
        result = self.validate_offline()
        self.assertEqual(result.reason, "cache_corrupt")

    def test_clock_rollback(self):
        future = (datetime.now() + timedelta(hours=1)).isoformat(timespec="seconds")
        self.write_cache(last_seen_at=future)
        result = self.validate_offline()
        self.assertEqual(result.reason, "clock_rollback")

    def test_online_return_refreshes_cache_after_offline(self):
        old = (datetime.now() - timedelta(days=2)).isoformat(timespec="seconds")
        self.write_cache(online_checked_at=old, last_seen_at=old)
        self.assertTrue(self.validate_offline().valid)
        self.assertTrue(self.validate_rows([self.row()]).valid)
        refreshed = load_encrypted_json(self.cache_path, "license-cache")
        self.assertGreater(datetime.fromisoformat(refreshed["online_checked_at"]), datetime.fromisoformat(old))

    def test_legacy_machine_bound_cache_is_migrated(self):
        now = datetime.now()
        legacy = {
            "license_key": self.key,
            "machine_code": self.machine,
            "valid": True,
            "offline_days": 7,
            "online_checked_at": (now - timedelta(days=1)).isoformat(timespec="seconds"),
            "last_seen_at": now.isoformat(timespec="seconds"),
            "message": "License hợp lệ",
        }
        save_encrypted_json(self.legacy_cache_path, legacy, "license-cache")
        result = self.validate_offline()
        self.assertTrue(result.valid)
        self.assertTrue(Path(self.cache_path).is_file())


if __name__ == "__main__":
    unittest.main()
