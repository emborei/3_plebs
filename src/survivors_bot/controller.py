"""XInput-compatible virtual gamepad output, provided by ViGEmBus/vgamepad."""
from __future__ import annotations

import time


class XboxController:
    def __init__(self) -> None:
        try:
            import vgamepad as vg
        except ImportError as exc:
            raise RuntimeError("Install the vgamepad bindings with packaging/install_vgamepad.py and install the ViGEmBus driver before running the bot") from exc
        self.vg = vg
        self.pad = vg.VX360Gamepad()

    def move(self, x: float, y: float) -> None:
        self.pad.left_joystick_float(
            x_value_float=max(-1.0, min(1.0, x)),
            y_value_float=max(-1.0, min(1.0, y)),
        )
        self.pad.update()

    def _tap(self, button, duration: float = 0.09) -> None:
        self.pad.press_button(button=button)
        self.pad.update()
        time.sleep(duration)
        self.pad.release_button(button=button)
        self.pad.update()

    def navigate_choices(self, index: int, horizontal: bool) -> None:
        """Move from the presumed first/top-left choice by its ordinal position."""
        if index <= 0:
            return
        if horizontal:
            button = self.vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_RIGHT
        else:
            button = self.vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_DOWN
        for _ in range(min(index, 5)):
            self._tap(button)
            time.sleep(0.10)

    def confirm(self) -> None:
        self._tap(self.vg.XUSB_BUTTON.XUSB_GAMEPAD_A, duration=0.12)

    def release_all(self) -> None:
        self.pad.left_joystick_float(x_value_float=0.0, y_value_float=0.0)
        for button in (
            self.vg.XUSB_BUTTON.XUSB_GAMEPAD_A,
            self.vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_UP,
            self.vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_DOWN,
            self.vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_LEFT,
            self.vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_RIGHT,
        ):
            self.pad.release_button(button=button)
        self.pad.update()


def foreground_title() -> str:
    """Return current foreground window title (Windows only)."""
    try:
        import win32gui
    except ImportError as exc:
        raise RuntimeError("This prototype currently supports Windows only") from exc
    hwnd = win32gui.GetForegroundWindow()
    return win32gui.GetWindowText(hwnd)


def game_is_foreground() -> bool:
    return "vampire survivors" in foreground_title().lower()
