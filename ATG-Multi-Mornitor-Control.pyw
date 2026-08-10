# -*- coding: utf-8 -*-
"""Entry point duy nhất cho bản phát hành ATG-Multi-Mornitor-Control one-file."""
import sys


def main():
    if "--launcher" in sys.argv:
        import launcher
        launcher.main()
    else:
        from settings import SettingsApp
        app = SettingsApp()
        app.mainloop()


if __name__ == "__main__":
    main()
