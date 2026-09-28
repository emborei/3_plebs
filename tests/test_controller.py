import sys
from types import SimpleNamespace

from survivors_bot import controller


class FakePad:
    def __init__(self):
        self.calls = []

    def left_joystick_float(self, **kwargs):
        self.calls.append(("stick", kwargs))

    def press_button(self, **kwargs):
        self.calls.append(("press", kwargs))

    def release_button(self, **kwargs):
        self.calls.append(("release", kwargs))

    def update(self):
        self.calls.append(("update",))


def test_xinput_adapter_contract_with_simulated_vigem(monkeypatch):
    names = ["A", "UP", "DOWN", "LEFT", "RIGHT"]
    enum = SimpleNamespace(**{f"XUSB_GAMEPAD_{name if name == 'A' else 'DPAD_' + name}": name for name in names})
    pad = FakePad()
    fake_vgamepad = SimpleNamespace(XUSB_BUTTON=enum, VX360Gamepad=lambda: pad)
    monkeypatch.setitem(sys.modules, "vgamepad", fake_vgamepad)
    monkeypatch.setattr(controller.time, "sleep", lambda _duration: None)

    gamepad = controller.XboxController()
    gamepad.move(-0.5, 0.25)
    gamepad.navigate_choices(1, horizontal=True)
    gamepad.confirm()
    gamepad.release_all()

    assert any(call[0] == "stick" and call[1]["x_value_float"] == -0.5 for call in pad.calls)
    assert any(call[0] == "press" and call[1]["button"] == "RIGHT" for call in pad.calls)
    assert any(call[0] == "press" and call[1]["button"] == "A" for call in pad.calls)
    assert pad.calls[-1] == ("update",)


def test_foreground_window_check_with_simulated_win32(monkeypatch):
    fake_win32 = SimpleNamespace(GetForegroundWindow=lambda: 42, GetWindowText=lambda _hwnd: "Vampire Survivors")
    monkeypatch.setitem(sys.modules, "win32gui", fake_win32)
    assert controller.game_is_foreground()
