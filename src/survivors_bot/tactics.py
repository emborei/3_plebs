"""Pure tactical logic for the upcoming scene-perception layer.

This module intentionally consumes detections rather than doing image recognition. That
keeps the danger policy testable without claiming that the current prototype can yet
reliably see enemies in a live game frame.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math


@dataclass(frozen=True)
class Threat:
    """A screen-relative threat in normalized 0..1 coordinates."""
    x: float
    y: float
    kind: str = "enemy"  # enemy, projectile, boss, telegraph
    confidence: float = 1.0
    vx: float = 0.0  # estimated normalized screen-space movement per second
    vy: float = 0.0


_THREAT_WEIGHT = {"enemy": 1.0, "projectile": 1.7, "boss": 1.5, "telegraph": 2.2}
_THREAT_RADIUS = {"enemy": 0.23, "projectile": 0.29, "boss": 0.31, "telegraph": 0.34}
_DIRECTIONS = tuple((math.cos(i * math.pi / 4), math.sin(i * math.pi / 4)) for i in range(8))


def choose_evasive_direction(
    threats: list[Threat],
    previous: tuple[float, float] | None = None,
    *,
    lookahead: float = 0.55,
    step: float = 0.16,
) -> tuple[float, float] | None:
    """Pick an 8-way move that minimizes predicted local threat exposure.

    The player is assumed to be near screen center. Threat motion is extrapolated a
    short distance; danger is weighted more heavily for projectiles and telegraphs.
    A small inertia term prevents rapid direction-flipping between similarly safe
    choices. Return None when no detected threat is close enough to justify dodging.
    """
    if not threats:
        return None
    valid = [t for t in threats if t.confidence >= 0.35 and 0 <= t.x <= 1 and 0 <= t.y <= 1]
    if not valid:
        return None
    predicted = [(t, t.x + t.vx * lookahead, t.y + t.vy * lookahead) for t in valid]
    center_danger = sum(
        _THREAT_WEIGHT.get(t.kind, 1.0) * t.confidence
        * max(0.0, 1.0 - math.hypot(px - 0.5, py - 0.5) / _THREAT_RADIUS.get(t.kind, 0.23)) ** 2
        for t, px, py in predicted
    )
    if center_danger < 0.015:
        return None

    best: tuple[float, float] | None = None
    best_cost = float("inf")
    for dx, dy in _DIRECTIONS:
        px, py = 0.5 + dx * step, 0.5 + dy * step
        cost = 0.0
        for threat, tx, ty in predicted:
            radius = _THREAT_RADIUS.get(threat.kind, 0.23)
            distance = math.hypot(px - tx, py - ty)
            penetration = max(0.0, 1.0 - distance / radius)
            cost += _THREAT_WEIGHT.get(threat.kind, 1.0) * threat.confidence * penetration**2
        if previous is not None:
            cost -= 0.035 * (dx * previous[0] + dy * previous[1])
        if cost < best_cost:
            best_cost, best = cost, (dx, dy)
    return best


@dataclass(frozen=True)
class BossEvidence:
    """Independent visual cues; timer_hint must never trigger a boss by itself."""
    boss_sprite: float = 0.0
    health_bar: float = 0.0
    nameplate: float = 0.0
    timer_hint: float = 0.0

    def score(self) -> float:
        values = (self.boss_sprite, self.health_bar, self.nameplate, self.timer_hint)
        if any(not 0.0 <= v <= 1.0 for v in values):
            raise ValueError("Boss cue confidence must be between 0 and 1")
        return 0.28 * self.boss_sprite + 0.42 * self.health_bar + 0.25 * self.nameplate + 0.05 * self.timer_hint

    def visual_cue_count(self) -> int:
        return sum(value >= 0.55 for value in (self.boss_sprite, self.health_bar, self.nameplate))


class BossState(str, Enum):
    NORMAL = "normal"
    SUSPECTED = "suspected"
    ACTIVE = "active"


class BossTracker:
    """Debounce screen evidence so flashes/UI noise do not cause state flapping."""
    def __init__(self, enter_frames: int = 2, clear_frames: int = 12) -> None:
        self.enter_frames = enter_frames
        self.clear_frames = clear_frames
        self.state = BossState.NORMAL
        self._positive_frames = 0
        self._missing_frames = 0

    def update(self, evidence: BossEvidence) -> BossState:
        score = evidence.score()
        plausible = score >= 0.52 and evidence.visual_cue_count() >= 2
        # A timer can raise suspicion, but never establishes an active boss fight.
        if plausible:
            self._positive_frames += 1
            self._missing_frames = 0
            self.state = BossState.ACTIVE if self._positive_frames >= self.enter_frames else BossState.SUSPECTED
        else:
            self._positive_frames = 0
            self._missing_frames += 1
            if self.state == BossState.NORMAL and (
                score >= 0.2 or evidence.visual_cue_count() > 0 or evidence.timer_hint >= 0.8
            ):
                self.state = BossState.SUSPECTED
            elif self._missing_frames >= self.clear_frames:
                self.state = BossState.NORMAL
            elif self.state == BossState.ACTIVE:
                self.state = BossState.SUSPECTED
        return self.state
