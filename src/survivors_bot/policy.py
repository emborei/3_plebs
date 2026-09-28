"""Beginner-friendly, unlock-tolerant choice ranking."""
from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher

WEAPON_PRIORITY = {
    "garlic": 100, "king bible": 96, "unholy vesper": 96,
    "magic wand": 92, "holy wand": 92, "santa water": 90,
    "la borra": 90, "lightning ring": 88, "thunder loop": 88,
    "axe": 84, "death spiral": 84, "runetracer": 82,
    "cross": 78, "heaven sword": 78, "whip": 77,
    "bloody tear": 82, "laurel": 85, "clock lancet": 74,
    "pentagram": 70, "fire wand": 73, "peachone": 70, "ebony wings": 70,
}
PASSIVE_PRIORITY = {
    "empty tome": 95, "duplicator": 94, "attractorb": 92,
    "spellbinder": 90, "candelabrador": 88, "spinach": 87,
    "hollow heart": 84, "armor": 75, "wings": 70,
    "crown": 68, "pummarola": 66, "bracer": 67,
    "clover": 64, "stone mask": 55,
}
ALIASES = {
    "bible": "king bible", "holy bible": "king bible",
    "evolved garlic": "soul eater", "attract orb": "attractorb",
    "unholy vespers": "unholy vesper",
}
BALANCED_BONUS = {
    "santa water": 7, "la borra": 7, "lightning ring": 6,
    "thunder loop": 6, "empty tome": 5, "duplicator": 5,
    "spinach": 7, "garlic": -12, "laurel": -8,
}


def normalize(text: str) -> str:
    text = re.sub(r"[^a-z0-9]+", " ", text.lower())
    return " ".join(text.split())


def canonicalize(text: str) -> str:
    normalized = normalize(text)
    return ALIASES.get(normalized, normalized)


def score_choice(label: str, profile: str = "Beginner safe") -> int:
    """Return a deterministic priority score; unknown choices remain viable."""
    name = canonicalize(label)
    if not name:
        return -1
    table = {**WEAPON_PRIORITY, **PASSIVE_PRIORITY}
    score = table.get(name)
    if score is None:
        # OCR may include level markers or a short subtitle around the actual name.
        for known, value in table.items():
            if known in name or name in known:
                score = value - min(12, max(0, len(name) - len(known)))
                break
    if score is None:
        best_ratio, best_score = max((SequenceMatcher(None, name, known).ratio(), value) for known, value in table.items())
        score = best_score - 18 if best_ratio >= 0.82 else 40
    if profile.lower().startswith("balanced"):
        score += BALANCED_BONUS.get(name, 0)
    return score


@dataclass(frozen=True)
class Choice:
    label: str
    x: int
    y: int
    confidence: float = 1.0


def choose_best(choices: list[Choice], profile: str = "Beginner safe") -> Choice | None:
    """Pick the most useful visible choice, preferring high-confidence OCR."""
    valid = [choice for choice in choices if choice.label.strip() and choice.confidence >= 0.35]
    if not valid:
        return None
    return max(valid, key=lambda c: (score_choice(c.label, profile), c.confidence, -c.y, -c.x))
