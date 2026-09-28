import numpy as np

import pytesseract
from survivors_bot.vision import analyze


def test_ocr_recognizes_visible_level_up_choices_without_real_tesseract(monkeypatch):
    words = ["Level", "Up!", "Garlic", "King", "Bible", "Stone", "Mask"]
    lefts = [350, 400, 250, 330, 380, 450, 500]
    tops = [80, 80, 250, 250, 250, 350, 350]
    lines = [1, 1, 2, 2, 2, 3, 3]
    data = {
        "text": words,
        "conf": ["95"] * len(words),
        "left": lefts,
        "top": tops,
        "block_num": [1] * len(words),
        "par_num": [1] * len(words),
        "line_num": lines,
    }
    monkeypatch.setattr(pytesseract, "image_to_data", lambda *_a, **_k: data)
    image = np.zeros((600, 800, 3), dtype=np.uint8)
    observation = analyze(image)
    assert observation.level_up_menu
    assert {choice.label for choice in observation.choices} >= {"garlic", "king bible", "stone mask"}
    assert observation.width == 800 and observation.height == 600
