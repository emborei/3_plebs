from survivors_bot.policy import Choice, choose_best, score_choice
from survivors_bot.strategy import orbit_vector


def test_beginner_sustain_and_build_options_rank_well():
    assert score_choice("Garlic") > score_choice("Stone Mask")
    assert score_choice("King Bible") > score_choice("Clover")
    assert score_choice("Attractorb") > score_choice("unknown item")
    assert score_choice("Garlic", "Beginner safe") > score_choice("Garlic", "Balanced damage")
    assert score_choice("Spinach", "Balanced damage") > score_choice("Spinach", "Beginner safe")


def test_choice_selection_ignores_empty_and_low_confidence_ocr():
    choices = [
        Choice("", 0, 0, 1.0),
        Choice("Garlic", 10, 10, 0.1),
        Choice("Magic Wand", 20, 20, 0.8),
        Choice("King Bible", 30, 30, 0.8),
    ]
    assert choose_best(choices).label == "King Bible"
    assert choose_best([Choice("Garlic", 0, 0, 0.1)]) is None


def test_orbit_is_normalized_and_changes_with_time():
    a = orbit_vector(1.0)
    b = orbit_vector(7.0)
    assert abs((a[0] ** 2 + a[1] ** 2) ** 0.5 - 1) < 1e-9
    assert a != b
