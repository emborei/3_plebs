"""User settings with defensive loading and recovery from malformed JSON."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
from typing import Any


@dataclass
class AppSettings:
    monitor: int = 1
    backend: str = "auto"
    model_path: str = ""
    labels_path: str = ""
    duration_minutes: int = 10
    scan_interval: float = 0.8
    profile: str = "Beginner safe"
    danger_mode: bool = False


class SettingsStore:
    def __init__(self, path: Path | None = None) -> None:
        root = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".config")) / "SurvivorsBuddy"
        self.path = path or root / "settings.json"

    def load(self) -> AppSettings:
        try:
            raw: dict[str, Any] = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("settings root must be an object")
            defaults = AppSettings()
            backend = raw.get("backend", defaults.backend)
            profile = raw.get("profile", defaults.profile)
            return AppSettings(
                monitor=max(1, int(raw.get("monitor", defaults.monitor))),
                backend=backend if backend in {"auto", "nvidia", "directml", "cpu"} else defaults.backend,
                model_path=str(raw.get("model_path", defaults.model_path))[:2048],
                labels_path=str(raw.get("labels_path", defaults.labels_path))[:2048],
                duration_minutes=max(1, min(60, int(raw.get("duration_minutes", defaults.duration_minutes)))),
                scan_interval=max(0.25, min(5.0, float(raw.get("scan_interval", defaults.scan_interval)))),
                profile=profile if profile in {"Beginner safe", "Balanced damage"} else defaults.profile,
                danger_mode=raw.get("danger_mode", defaults.danger_mode) is True,
            )
        except FileNotFoundError:
            return AppSettings()
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                self.path.replace(self.path.with_suffix(".corrupt.json"))
            except OSError:
                pass
            return AppSettings()

    def save(self, settings: AppSettings) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(".tmp")
        temp.write_text(json.dumps(asdict(settings), indent=2), encoding="utf-8")
        temp.replace(self.path)
