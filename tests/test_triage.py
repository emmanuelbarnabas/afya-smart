"""Tests for the rule-based triage in triage.py."""

import pytest

from triage import triage


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def base(symptoms=None):
    """Dictionary with the common keys always present so each case stays tiny."""
    return {"age": 30, "fever": False, **(symptoms or {})}


# --------------------------------------------------------------------------- #
# RED (emergency) cases
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("symptoms,expected", [
    # chest pain alone -> RED
    ({"chest_pain": True}, ("RED", "EMERGENCY - chest pain")),
    # breathing difficulty alone -> RED
    ({"breathing_difficulty": True}, ("RED", "EMERGENCY - breathing difficulty")),
    # severe bleeding alone -> RED
    ({"severe_bleeding": True}, ("RED", "EMERGENCY - severe bleeding")),
    # unconsciousness (unresponsive) alone -> RED
    ({"loss_of_consciousness": True}, ("RED", "EMERGENCY - unconsciousness")),
    # convulsion during the day alone -> RED
    ({"convulsion": True}, ("RED", "EMERGENCY - convulsion")),
    # infant under 1 year (age 0) with fever -> RED (pre-referral)
    ({"fever": True, "age": 0}, ("RED", "EMERGENCY - infant with fever")),
    # infant with fever plus another sign -> RED, reason lists both
    ({"fever": True, "age": 0, "fever_days": 2},
     ("RED", "EMERGENCY - infant with fever")),
    # all three at once -> still RED, reason lists all of them
    ({"chest_pain": True, "breathing_difficulty": True, "severe_bleeding": True},
     ("RED", "EMERGENCY - chest pain, breathing difficulty, severe bleeding")),
    # strict falsy values must not hide a real RED flag
    ({"chest_pain": 0}, ("GREEN", "ROUTINE - no emergency features found")),
    ({"chest_pain": False}, ("GREEN", "ROUTINE - no emergency features found")),
    ({"chest_pain": "no"}, ("GREEN", "ROUTINE - no emergency features found")),
    ({"chest_pain": "0"}, ("GREEN", "ROUTINE - no emergency features found")),
    ({"chest_pain": "false"}, ("GREEN", "ROUTINE - no emergency features found")),
])
def test_red_rules(symptoms, expected):
    assert triage(base(symptoms)) == expected


# --------------------------------------------------------------------------- #
# YELLOW (non-emergency but at risk) cases
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("symptoms,expected", [
    # fever alone -> YELLOW
    ({"fever": True}, ("YELLOW", "WATCH - fever")),
    # age < 5 -> YELLOW ("child")
    ({"age": 2}, ("YELLOW", "WATCH - age < 5 or > 65")),
    # age > 65 -> YELLOW ("elderly")
    ({"age": 70}, ("YELLOW", "WATCH - age < 5 or > 65")),
    # both fever and age -> YELLOW, reason lists both
    ({"fever": True, "age": 70}, ("YELLOW", "WATCH - fever, age < 5 or > 65")),
    # fever lasting 5+ days is prolonged fever -> YELLOW reason grows
    ({"fever": True, "fever_days": 7}, ("YELLOW", "WATCH - fever, prolonged fever (5+ days)")),
    # a short fever (2 days) stays a plain fever
    ({"fever": True, "fever_days": 2}, ("YELLOW", "WATCH - fever")),
    # missing/invalid fever_days never escalates on its own
    ({"fever": True, "fever_days": None}, ("YELLOW", "WATCH - fever")),
    ({"fever": True, "fever_days": "unknown"}, ("YELLOW", "WATCH - fever")),
    # age 0 WITHOUT fever is still just a child -> YELLOW
    ({"fever": False, "age": 0}, ("YELLOW", "WATCH - age < 5 or > 65")),
    # missing age key behaves like age 0 (no age information)
    ({"fever": True}, ("YELLOW", "WATCH - fever")),
])
def test_yellow_rules(symptoms, expected):
    assert triage(base(symptoms)) == expected


# --------------------------------------------------------------------------- #
# GREEN (routine) cases
# --------------------------------------------------------------------------- #

def test_green_routine():
    symptoms = base({"headache": True, "cough": True})
    level, reason = triage(symptoms)
    assert level == "GREEN"
    assert "ROUTINE" in reason


# --------------------------------------------------------------------------- #
# The safety rule: unsure -> go UP, never down
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("value", [
    "maybe",
    "unknown",
    "idk",
    "yes maybe",
])
def test_unsure_values_escalate(value):
    # A chest-pain value of "maybe"/"unknown" is not a real emergency flag,
    # so the rule-based engine is unsure and escalates the patient.
    symptoms = base({"chest_pain": value})
    level, reason = triage(symptoms)
    # Only a real emergency flag is a definitive RED; everything else is at
    # least YELLOW (and never downgraded to GREEN).
    assert level in ("RED", "YELLOW"), reason


# --------------------------------------------------------------------------- #
# Age boundary values
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("age,expected_level", [
    # 0 IS a child (age < 5) -- "age 0" is not the same as "no age given".
    # base() will never produce age 0 unless we pass it explicitly.
    # (handled below)
    (1, "YELLOW"),   # baby
    (5, "GREEN"),    # exactly 5 is not "< 5"
    (65, "GREEN"),   # not > 65
    (66, "YELLOW"),  # elderly
    (100, "YELLOW"),
])
def test_age_boundary_values(age, expected_level):
    level, _ = triage(base({"fever": False, "age": age}))
    assert level == expected_level


# --------------------------------------------------------------------------- #
# Cleanliness: `reason` is always a non-empty string
# --------------------------------------------------------------------------- #

def test_reason_always_returns_a_string():
    level, reason = triage(base({"chest_pain": True}))
    assert isinstance(level, str)
    assert isinstance(reason, str)
    assert len(reason) > 0
    assert level in ("RED", "YELLOW", "GREEN")
