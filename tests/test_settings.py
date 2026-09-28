import json

from survivors_bot.settings import SettingsStore


def test_settings_are_clamped_and_unknown_backend_is_reset(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"duration_minutes": 999, "monitor": 0, "backend": "mystery", "scan_interval": 0.01}))
    settings = SettingsStore(path).load()
    assert settings.duration_minutes == 60
    assert settings.monitor == 1
    assert settings.backend == "auto"
    assert settings.scan_interval == 0.25


def test_corrupt_settings_are_preserved_and_recovered(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("not-json")
    settings = SettingsStore(path).load()
    assert settings.duration_minutes == 10
    assert (tmp_path / "settings.corrupt.json").exists()
