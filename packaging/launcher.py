"""PyInstaller entrypoint with a bounded crash guardian."""
from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import time


def _notify(text: str) -> None:
    if os.name == "nt":
        ctypes.windll.user32.MessageBoxW(None, text, "Survivors Buddy recovery", 0x30)


def main() -> int:
    if not getattr(sys, "frozen", False):
        from survivors_bot.gui import launch
        return launch()
    if "--_guardian-child" in sys.argv:
        from survivors_bot.gui import launch
        return launch()
    exe = sys.executable
    for attempt in range(3):
        process = subprocess.Popen([exe, "--_guardian-child"])
        code = process.wait()
        if code == 0:
            return 0
        if attempt >= 2:
            _notify("The app stopped unexpectedly three times. No further restart was attempted. Check the local app.log and restart manually.")
            return code or 1
        _notify(f"The app stopped unexpectedly (exit {code}). It will restart once more ({attempt + 1}/2). If this repeats, it will stop safely.")
        time.sleep(1.0 + attempt)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
