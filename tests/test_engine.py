from types import SimpleNamespace

from survivors_bot import controller, vision
from survivors_bot.engine import BotEngine, threat_kind
from survivors_bot.gpu import runtime_info
from survivors_bot.policy import Choice
from survivors_bot.vision import Observation


def test_detection_class_names_are_mapped_conservatively():
    assert threat_kind("enemy_bat") == "enemy"
    assert threat_kind("incoming_projectile") == "projectile"
    assert threat_kind("boss_reaper") == "boss"
    assert threat_kind("boss_health_bar") is None
    assert threat_kind("boss_nameplate") is None
    assert threat_kind("attack_telegraph") == "telegraph"
    assert threat_kind("xp_gem") is None


def test_provider_report_always_has_safe_selection():
    info = runtime_info("auto")
    assert info.selected
    assert isinstance(info.available, tuple)


def test_engine_can_cancel_safely_while_waiting_for_focus(monkeypatch):
    monkeypatch.setattr(controller, "game_is_foreground", lambda: False)
    monkeypatch.setattr(controller, "XboxController", lambda: (_ for _ in ()).throw(AssertionError("controller must not be created")))
    BotEngine().run(
        monitor=1, duration_seconds=10, interval=.25,
        stop_requested=lambda: True, log=lambda _message: None,
    )


def test_engine_selects_once_and_releases_controller(monkeypatch):
    events = []

    class FakePad:
        def move(self, *values): events.append(("move", values))
        def navigate_choices(self, index, horizontal): events.append(("navigate", index, horizontal))
        def confirm(self): events.append(("confirm",))
        def release_all(self): events.append(("release",))

    monkeypatch.setattr(controller, "game_is_foreground", lambda: True)
    monkeypatch.setattr(controller, "XboxController", FakePad)
    monkeypatch.setattr(vision, "capture_monitor", lambda _monitor: SimpleNamespace(shape=(600, 800, 3)))
    observation = Observation(
        800, 600, "Level Up Garlic King Bible", (
            Choice("Garlic", 200, 200, .95),
            Choice("King Bible", 400, 300, .95),
        ), True,
    )
    monkeypatch.setattr(vision, "analyze", lambda _frame: observation)
    checks = 0

    def stop_soon():
        nonlocal checks
        checks += 1
        return checks > 5

    BotEngine().run(
        monitor=1, duration_seconds=10, interval=.25,
        stop_requested=stop_soon, log=lambda _message: None,
    )
    assert ("confirm",) in events
    assert any(event[0] == "navigate" for event in events)
    assert events[-1] == ("release",)
