"""Movement-only survival pattern. Scene-aware navigation is a planned next phase."""
from __future__ import annotations

import math


def orbit_vector(seconds: float) -> tuple[float, float]:
    """Smooth orbit with periodic direction changes and gentle radial variation."""
    cycle = int(seconds // 20.0)
    direction = 1.0 if cycle % 2 == 0 else -1.0
    phase = (seconds % 20.0) * (2 * math.pi / 14.0) * direction
    radius = 0.68 + 0.20 * math.sin(seconds * 0.31)
    radial = 0.16 * math.cos(seconds * 0.31)
    # Tangential movement keeps changing direction; radial drift avoids a fixed loop.
    x = radius * math.cos(phase) - direction * 0.58 * math.sin(phase) + radial * math.cos(phase)
    y = radius * math.sin(phase) + direction * 0.58 * math.cos(phase) + radial * math.sin(phase)
    magnitude = math.hypot(x, y)
    return (x / magnitude, y / magnitude) if magnitude > 1 else (x, y)
