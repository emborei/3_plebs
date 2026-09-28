"""Visible-pixel capture and deliberately cautious OCR-based menu detection."""
from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
import os
import re
import sys
from pathlib import Path

from .policy import Choice, PASSIVE_PRIORITY, WEAPON_PRIORITY, canonicalize, normalize

KNOWN_NAMES = sorted({*WEAPON_PRIORITY, *PASSIVE_PRIORITY}, key=len, reverse=True)
MENU_MARKERS = ("level up", "choose an upgrade", "choose your upgrade", "pick an upgrade", "level up!")


@dataclass(frozen=True)
class Observation:
    width: int
    height: int
    text: str
    choices: tuple[Choice, ...]
    level_up_menu: bool


def capture_monitor(monitor: int = 1):
    """Capture a monitor as an RGB numpy array. Monitor 1 is the primary display."""
    import mss
    import numpy as np

    with mss.mss() as capture:
        monitors = capture.monitors
        if monitor < 1 or monitor >= len(monitors):
            raise ValueError(f"Monitor {monitor} unavailable; found {len(monitors) - 1} display(s)")
        shot = np.asarray(capture.grab(monitors[monitor]))
        return shot[:, :, :3][:, :, ::-1].copy()


def _line_records(data: dict) -> list[tuple[str, int, int, float, list[tuple[str, int, int, float]]]]:
    groups: dict[tuple[int, int, int], list[tuple[str, int, int, float]]] = {}
    count = len(data.get("text", []))
    for i in range(count):
        word = (data["text"][i] or "").strip()
        try:
            conf = float(data["conf"][i]) / 100
            x, y = int(data["left"][i]), int(data["top"][i])
        except (ValueError, TypeError):
            continue
        if not word or conf < 0.25:
            continue
        key = (int(data["block_num"][i]), int(data["par_num"][i]), int(data["line_num"][i]))
        groups.setdefault(key, []).append((word, x, y, conf))
    lines = []
    for words in groups.values():
        words.sort(key=lambda part: part[1])
        line = " ".join(p[0] for p in words)
        confidence = sum(p[3] for p in words) / len(words)
        lines.append((line, min(p[1] for p in words), min(p[2] for p in words), confidence, words))
    return lines


def _matched_name(line: str) -> tuple[str | None, float]:
    """Return the best match for one OCR phrase, retained for unit diagnostics."""
    normalized = canonicalize(line)
    tokens = normalized.split()
    best_name, best_ratio = None, 0.0
    for name in KNOWN_NAMES:
        target = normalize(name)
        if target in normalized:
            return name, 1.0
        target_tokens = target.split()
        for start in range(max(1, len(tokens) - len(target_tokens) + 1)):
            window = " ".join(tokens[start : start + len(target_tokens)])
            ratio = SequenceMatcher(None, window, target).ratio()
            if ratio > best_ratio:
                best_name, best_ratio = name, ratio
    return (best_name, best_ratio) if best_ratio >= 0.73 else (None, best_ratio)


def _matched_names(words: list[tuple[str, int, int, float]]) -> list[tuple[str, int, int, float]]:
    """Find multiple item names on one OCR line (common in horizontal choice cards)."""
    tokens: list[str] = []
    positions: list[tuple[int, int, float]] = []
    for word, x, y, confidence in words:
        parts = normalize(word).split()
        tokens.extend(parts)
        positions.extend([(x, y, confidence)] * len(parts))
    matches = []
    index = 0
    while index < len(tokens):
        best_name, best_ratio, best_length = None, 0.0, 0
        for name in KNOWN_NAMES:
            target = normalize(name).split()
            window = tokens[index : index + len(target)]
            if len(window) != len(target):
                continue
            ratio = SequenceMatcher(None, " ".join(window), " ".join(target)).ratio()
            if ratio > best_ratio:
                best_name, best_ratio, best_length = name, ratio, len(target)
        if best_name and best_ratio >= 0.73:
            x, y, confidence = positions[index]
            matches.append((best_name, x, y, min(confidence, best_ratio)))
            index += max(1, best_length)
        else:
            index += 1
    return matches


def analyze(image) -> Observation:
    """Read likely level-up options from visible text; never infer a menu from game state."""
    import cv2
    import pytesseract

    command = os.environ.get("TESSERACT_CMD")
    if not command and getattr(sys, "frozen", False):
        bundled = Path(sys.executable).parent / "resources" / "tesseract" / "tesseract.exe"
        if bundled.exists():
            command = str(bundled)
    if command:
        pytesseract.pytesseract.tesseract_cmd = command
    height, width = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    scaled = cv2.resize(gray, None, fx=1.5, fy=1.5, interpolation=cv2.INTER_CUBIC)
    _, binary = cv2.threshold(scaled, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    data = pytesseract.image_to_data(binary, config="--psm 11", output_type=pytesseract.Output.DICT)
    lines = _line_records(data)
    text = " ".join(line[0] for line in lines)
    low_text = normalize(text)
    recognized: list[Choice] = []
    for line, _x, _y, confidence, words in lines:
        for name, x, y, ratio in _matched_names(words):
            px, py = int(x / 1.5), int(y / 1.5)
            if name and 0.12 * width <= px <= 0.88 * width and 0.12 * height <= py <= 0.88 * height:
                recognized.append(Choice(name, px, py, min(1.0, confidence * ratio)))

    heading_present = any(marker in low_text for marker in MENU_MARKERS)
    menu = heading_present or len(recognized) >= 2
    return Observation(width, height, text, tuple(recognized), menu)
