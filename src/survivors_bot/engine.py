"""Supervised run loop with bounded recovery and fail-safe controller cleanup."""
from __future__ import annotations

import time
from typing import Callable

from .policy import choose_best
from .strategy import orbit_vector
from .tactics import BossEvidence, BossState, BossTracker, Threat, choose_evasive_direction


def threat_kind(label: str) -> str | None:
    name = label.lower().replace("_", " ")
    if ("health" in name and "bar" in name) or "nameplate" in name:
        return None  # UI evidence for boss state, not a world-space collision
    if any(word in name for word in ("telegraph", "warning", "hazard", "explosion")):
        return "telegraph"
    if any(word in name for word in ("projectile", "shot", "bullet", "fireball")):
        return "projectile"
    if "boss" in name or "reaper" in name:
        return "boss"
    if any(word in name for word in ("enemy", "zombie", "monster", "bat", "skeleton", "pipeestrello")):
        return "enemy"
    return None


class BotEngine:
    """Execute a bounded, foreground-only game session. Exceptions fail closed."""
    def run(
        self,
        *,
        monitor: int,
        duration_seconds: int,
        interval: float,
        stop_requested: Callable[[], bool],
        log: Callable[[str], None] = print,
        frame_ready: Callable[[object, object, list], None] | None = None,
        model_path: str = "",
        labels_path: str = "",
        backend: str = "auto",
        danger_mode: bool = False,
        profile: str = "Beginner safe",
    ) -> None:
        from .controller import XboxController, game_is_foreground
        from .vision import analyze, capture_monitor

        if not game_is_foreground():
            log("Armed safely; switch to the Vampire Survivors window within 30 seconds. No input is sent while waiting.")
            focus_deadline = time.monotonic() + 30
            while not game_is_foreground() and time.monotonic() < focus_deadline and not stop_requested():
                time.sleep(0.25)
            if stop_requested():
                log("Start cancelled before the game was focused; no input was sent.")
                return
            if not game_is_foreground():
                raise RuntimeError("Vampire Survivors did not become the foreground window; no controller input was sent.")
        detector = None
        if danger_mode:
            if not model_path:
                raise RuntimeError("Danger-aware mode needs a compatible ONNX model and label file.")
            label_path = labels_path or model_path.rsplit(".", 1)[0] + ".txt"
            from .detector import OnnxYoloDetector
            detector = OnnxYoloDetector(model_path, label_path, backend)
            log(f"Scene model ready: {detector.provider}; labels loaded from {label_path}.")

        pad = None
        failures = 0
        start = time.monotonic()
        next_scan = 0.0
        was_menu = False
        missed_menu = 0
        last_move = orbit_vector(0)
        latest_detections = []
        boss_tracker = BossTracker()
        boss_state = BossState.NORMAL
        last_log = start

        def release_safely() -> None:
            if pad is None:
                return
            try:
                pad.release_all()
            except Exception as release_error:
                log(f"Controller release warning: {release_error}")

        try:
            while time.monotonic() - start < duration_seconds and not stop_requested():
                now = time.monotonic()
                if not game_is_foreground():
                    release_safely()
                    log("Paused: game lost focus. Inputs released until focus returns.")
                    while not game_is_foreground() and time.monotonic() - start < duration_seconds and not stop_requested():
                        time.sleep(0.25)
                    continue
                try:
                    if pad is None:
                        pad = XboxController()
                    if now >= next_scan:
                        frame = capture_monitor(monitor)
                        observation = analyze(frame)
                        detections = detector.detect(frame) if detector is not None else []
                        latest_detections = detections
                        if detector is not None:
                            evidence = BossEvidence(
                                boss_sprite=max((d.confidence for d in detections if threat_kind(d.label) == "boss"), default=0.0),
                                health_bar=max((d.confidence for d in detections if "health" in d.label.lower() and "bar" in d.label.lower()), default=0.0),
                                nameplate=max((d.confidence for d in detections if "nameplate" in d.label.lower() or "boss name" in d.label.lower()), default=0.0),
                            )
                            next_boss_state = boss_tracker.update(evidence)
                            if next_boss_state != boss_state:
                                log(f"Boss state: {next_boss_state.value} (visual cues; timer alone is never enough).")
                                boss_state = next_boss_state
                        if frame_ready:
                            frame_ready(frame, observation, detections)
                        next_scan = time.monotonic() + interval
                        failures = 0
                        if observation.level_up_menu:
                            missed_menu = 0
                            pad.move(0.0, 0.0)
                            if not was_menu:
                                best = choose_best(list(observation.choices), profile)
                                if best and observation.choices:
                                    xs = [c.x for c in observation.choices]
                                    ys = [c.y for c in observation.choices]
                                    horizontal = max(xs) - min(xs) > max(ys) - min(ys)
                                    ordered = sorted(observation.choices, key=(lambda c: (c.x, c.y)) if horizontal else (lambda c: (c.y, c.x)))
                                    pad.navigate_choices(ordered.index(best), horizontal)
                                    pad.confirm()
                                    log(f"Level choice: {best.label}")
                                else:
                                    log("Upgrade screen detected but text was unclear; waiting safely.")
                            was_menu = True
                        elif was_menu:
                            missed_menu += 1
                            if missed_menu >= 2:
                                was_menu, missed_menu = False, 0

                    if not was_menu:
                        move = None
                        if detector is not None and danger_mode:
                            threats = []
                            for item in latest_detections:
                                kind = threat_kind(item.label)
                                if kind:
                                    cx, cy = item.center
                                    threats.append(Threat(cx / frame.shape[1], cy / frame.shape[0], kind, item.confidence))
                            move = choose_evasive_direction(threats, last_move)
                        if move is None:
                            move = orbit_vector(time.monotonic() - start)
                        last_move = move
                        pad.move(*move)
                    if time.monotonic() - last_log > 30:
                        log(f"Session active: {int(time.monotonic() - start)}s / {duration_seconds}s")
                        last_log = time.monotonic()
                except Exception as exc:
                    failures += 1
                    release_safely()
                    log(f"Recoverable run error {failures}/3: {exc}; controller release attempted.")
                    if failures >= 3:
                        raise RuntimeError("Three consecutive capture/inference/input failures; stopped safely.") from exc
                    pad = None  # recreate controller on retry
                    time.sleep(0.4 * failures)
                time.sleep(0.06)
        finally:
            release_safely()
            log("Stopped; controller output release attempted.")
