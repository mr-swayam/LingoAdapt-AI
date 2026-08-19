from app.services.learner_context import estimate_level


def test_estimate_level_bands() -> None:
    assert estimate_level(0) == "A1"
    assert estimate_level(14.9) == "A1"
    assert estimate_level(15) == "A2"
    assert estimate_level(34.9) == "A2"
    assert estimate_level(35) == "B1"
    assert estimate_level(54.9) == "B1"
    assert estimate_level(55) == "B2"
    assert estimate_level(74.9) == "B2"
    assert estimate_level(75) == "C1"
    assert estimate_level(89.9) == "C1"
    assert estimate_level(90) == "C2"
    assert estimate_level(100) == "C2"
