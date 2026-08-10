# -*- coding: utf-8 -*-
import sys
import types
import unittest
from unittest import mock

import common
import settings


class BrandingMigrationTests(unittest.TestCase):
    def test_canonical_names(self):
        self.assertEqual(common.APP_NAME, "ATG-Multi-Mornitor-Control")
        self.assertEqual(settings.RUN_KEY_NAME, common.APP_NAME)
        self.assertEqual(settings.TASK_SHUTDOWN, common.APP_NAME + "-Shutdown")
        self.assertEqual(settings.TASK_RESTART, common.APP_NAME + "-Restart")
        self.assertEqual(settings.WINDOWS_APP_ID, "AnNguyen.ATGMultiMornitorControl")

    def test_startup_migrates_legacy_registry_value(self):
        calls = []
        fake = types.SimpleNamespace(
            HKEY_CURRENT_USER=object(), KEY_SET_VALUE=1, REG_SZ=1,
            OpenKey=lambda *args: object(), CloseKey=lambda key: None,
            DeleteValue=lambda key, name: calls.append(("delete", name)),
            SetValueEx=lambda key, name, reserved, kind, value: calls.append(("set", name)),
        )
        with mock.patch.object(settings, "IS_WINDOWS", True), \
             mock.patch.dict(sys.modules, {"winreg": fake}), \
             mock.patch.object(settings, "get_launcher_command", return_value=["app.exe", "--launcher"]):
            settings.set_run_on_startup(True)
        self.assertIn(("delete", "VLCSignage"), calls)
        self.assertIn(("set", common.APP_NAME), calls)

    def test_scheduled_task_migrates_legacy_name(self):
        completed = mock.Mock(returncode=0, stderr="", stdout="")
        with mock.patch.object(settings, "IS_WINDOWS", True), \
             mock.patch.object(settings.subprocess, "run", return_value=completed) as run:
            settings.set_scheduled_task(
                settings.TASK_SHUTDOWN, True, "22:00", "shutdown",
                (settings.LEGACY_TASK_SHUTDOWN,),
            )
        commands = [call.args[0] for call in run.call_args_list]
        self.assertIn(["schtasks", "/Delete", "/TN", "VLCSignage_Shutdown", "/F"], commands)
        self.assertTrue(any(cmd[:4] == ["schtasks", "/Create", "/TN", settings.TASK_SHUTDOWN]
                            for cmd in commands))


if __name__ == "__main__":
    unittest.main()
