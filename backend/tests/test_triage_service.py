"""Tests za triage service — rule engine ya urgency."""
from app.models.triage import UrgencyLevel
from app.services.triage import classify, outcome_for_urgency, parse_answer, TRIAGE_QUESTIONS


def _answers(breathing=None, conscious=None, bleeding=None, fever_days=0, pain_level=0, risk_group=0):
    return {
        "breathing": breathing,
        "conscious": conscious,
        "bleeding": bleeding,
        "fever_days": fever_days,
        "pain_level": pain_level,
        "risk_group": risk_group,
    }


def test_all_critical_yes_is_emergency():
    urgency, conf = classify(_answers(breathing=True, conscious=True, bleeding=True))
    assert urgency == UrgencyLevel.EMERGENCY
    assert conf >= 0.9


def test_two_critical_yes_is_emergency():
    urgency, _ = classify(_answers(breathing=True, conscious=False, bleeding=True))
    assert urgency == UrgencyLevel.EMERGENCY


def test_one_critical_with_risk_group_is_emergency():
    urgency, _ = classify(_answers(breathing=True, risk_group=2))
    assert urgency == UrgencyLevel.EMERGENCY


def test_one_critical_without_risk_is_urgent():
    urgency, _ = classify(_answers(bleeding=True, risk_group=0))
    assert urgency == UrgencyLevel.URGENT


def test_long_fever_is_urgent():
    urgency, _ = classify(_answers(fever_days=2))
    assert urgency == UrgencyLevel.URGENT


def test_severe_pain_is_urgent():
    urgency, _ = classify(_answers(pain_level=3))
    assert urgency == UrgencyLevel.URGENT


def test_mild_symptoms_are_routine():
    urgency, _ = classify(_answers(fever_days=1, pain_level=1))
    assert urgency == UrgencyLevel.ROUTINE


def test_no_symptoms_is_self_care():
    urgency, _ = classify(_answers())
    assert urgency == UrgencyLevel.SELF_CARE


def test_empty_answers_default_urgent_safety():
    urgency, conf = classify({})
    assert urgency == UrgencyLevel.URGENT
    assert conf < 0.5  # low confidence — safe default


def test_questions_are_six_or_fewer():
    assert 4 <= len(TRIAGE_QUESTIONS) <= 6


def test_parse_answer_maps_correctly():
    q = TRIAGE_QUESTIONS[0]  # breathing
    assert parse_answer(q, "1") is True
    assert parse_answer(q, "0") is False
    assert parse_answer(q, "9") is None


def test_outcome_mapping():
    assert outcome_for_urgency(UrgencyLevel.EMERGENCY) == "emergency_directed"
    assert outcome_for_urgency(UrgencyLevel.ROUTINE) == "slot_booked"
    assert outcome_for_urgency(UrgencyLevel.SELF_CARE) == "self_care_given"
