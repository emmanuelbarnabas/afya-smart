"""Tests za ML triage — model halisi (ml-v1) + safety override + fallback."""
from app.models.triage import UrgencyLevel
from app.services import ml_triage
from app.services.ml_triage import classify as ml_classify
from app.services.triage import classify_full, parse_answer, TRIAGE_QUESTIONS


def _answers(breathing=None, conscious=None, bleeding=None, fever_days=0, pain_level=0, risk_group=0):
    return {
        "breathing": breathing,
        "conscious": conscious,
        "bleeding": bleeding,
        "fever_days": fever_days,
        "pain_level": pain_level,
        "risk_group": risk_group,
    }


# ---------------------------------------------------------------- model loaded
def test_model_is_loaded():
    info = ml_triage.get_model_info()
    assert info is not None
    assert info["loaded"] is True
    assert info["version"] == "ml-v1"
    assert info["algorithm"] == "gradient_boosting"
    assert info["accuracy"] and info["accuracy"] > 0.85


def test_model_artifact_metadata():
    info = ml_triage.get_model_info()
    assert info["n_samples"] == 12000
    assert 0 < info["recall_emergency"] < 1


# ---------------------------------------------------------------- ml predictions
def test_all_critical_is_emergency_with_high_confidence():
    # conscious=0 (hajiamshi) ndiyo hatari — USSD semantics
    urgency, conf, version = ml_classify(_answers(breathing=True, conscious=False, bleeding=True))
    assert urgency == UrgencyLevel.EMERGENCY
    assert conf >= 0.9
    assert version.startswith("ml-v1")


def test_two_critical_is_emergency():
    urgency, _, _ = ml_classify(_answers(breathing=True, conscious=False, bleeding=False))
    assert urgency == UrgencyLevel.EMERGENCY


def test_one_critical_with_risk_is_emergency():
    urgency, _, _ = ml_classify(_answers(breathing=True, risk_group=2))
    assert urgency == UrgencyLevel.EMERGENCY


def test_one_critical_without_risk_is_urgent():
    urgency, _, _ = ml_classify(_answers(bleeding=True, risk_group=0))
    assert urgency == UrgencyLevel.URGENT


def test_long_fever_is_urgent():
    urgency, conf, _ = ml_classify(_answers(fever_days=2))
    assert urgency == UrgencyLevel.URGENT
    assert conf >= 0.5


def test_severe_pain_is_urgent():
    urgency, _, _ = ml_classify(_answers(pain_level=3))
    assert urgency == UrgencyLevel.URGENT


def test_mild_symptoms_are_routine():
    urgency, _, _ = ml_classify(_answers(fever_days=1, pain_level=1))
    assert urgency == UrgencyLevel.ROUTINE


def test_no_symptoms_is_self_care():
    urgency, conf, _ = ml_classify(_answers())
    assert urgency == UrgencyLevel.SELF_CARE
    assert conf >= 0.5


def test_model_version_string():
    _, _, version = ml_classify(_answers())
    assert version in ("ml-v1", "ml-v1+safety", "rules-v1")


# ---------------------------------------------------------------- safety override
def test_safety_override_critical_flags_always_emergency():
    # Hata kama model inge-sema routine, 2+ critical flags → EMERGENCY
    urgency, _, version = ml_classify(_answers(breathing=True, bleeding=True))
    assert urgency == UrgencyLevel.EMERGENCY
    # Kesi hii model inaiambia emergency yenyewe, kwa hiyo version ni ml-v1


def test_safety_critical_escalation():
    # critical flag moja + model inasema routine → lazima ipande hadi urgent au zaidi
    urgency, _, _ = ml_classify(_answers(bleeding=True, pain_level=0))
    assert _LABELS_ORDER.index(urgency) <= _LABELS_ORDER.index(UrgencyLevel.URGENT)


_LABELS_ORDER = [UrgencyLevel.EMERGENCY, UrgencyLevel.URGENT, UrgencyLevel.ROUTINE, UrgencyLevel.SELF_CARE]


# ---------------------------------------------------------------- fallback
def test_empty_answers_falls_back_to_rules_safety(monkeypatch):
    # Model haipo → rules fallback
    monkeypatch.setattr(ml_triage._holder, "get", lambda: None)
    urgency, conf, version = ml_classify({})
    assert urgency == UrgencyLevel.URGENT
    assert conf < 0.5
    assert version == "rules-v1"


def test_classify_full_returns_triple():
    result = classify_full(_answers(fever_days=2))
    assert len(result) == 3
    urgency, conf, version = result
    assert urgency == UrgencyLevel.URGENT
    assert 0.0 <= conf <= 1.0
    assert isinstance(version, str)


def test_entry_point_still_works():
    """classify() ya rules module bado inafanya kazi (backward compat)."""
    from app.services.triage import classify

    urgency, conf = classify(_answers(fever_days=2))
    assert urgency == UrgencyLevel.URGENT
    assert 0.0 <= conf <= 1.0


def test_questions_are_six_or_fewer():
    assert 4 <= len(TRIAGE_QUESTIONS) <= 6


def test_parse_answer_maps_correctly():
    q = TRIAGE_QUESTIONS[0]
    assert parse_answer(q, "1") is True
    assert parse_answer(q, "0") is False
    assert parse_answer(q, "9") is None
