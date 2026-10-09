"""Tests za safety alert — under-triage threshold kwenye /triage-accuracy."""
from app.models.triage import TriageSession


def _add_sessions(db_session, facility, patient, rows):
    for system, clinician in rows:
        db_session.add(
            TriageSession(
                patient_id=patient.id,
                facility_id=facility.id,
                answers={},
                urgency=system,
                clinician_urgency=clinician,
            )
        )
    db_session.commit()


def test_alert_false_when_undertriage_low(client, facility, patient, db_session):
    # 20 reviewed, 2 under-triage = 10% < 15% threshold
    rows = [("routine", "routine")] * 18 + [("routine", "self_care")] * 2
    _add_sessions(db_session, facility, patient, rows)
    resp = client.get(f"/api/v1/facilities/{facility.id}/analytics/triage-accuracy?days=30")
    data = resp.json()
    assert data["alert"] is False
    assert data["threshold"] == 0.15


def test_alert_true_when_undertriage_high(client, facility, patient, db_session):
    # 20 reviewed, 5 under-triage = 25% >= 15% threshold
    # under-triage = mfumo ulisema PUNGUfu (routine) kuliko clinician (urgent)
    rows = [("routine", "routine")] * 15 + [("routine", "urgent")] * 5
    _add_sessions(db_session, facility, patient, rows)
    resp = client.get(f"/api/v1/facilities/{facility.id}/analytics/triage-accuracy?days=30")
    data = resp.json()
    assert data["undertriaged"] == 5
    assert data["alert"] is True


def test_alert_false_when_no_feedback_yet(client, facility, patient, db_session):
    # Hakuna clinician feedback — hakuna alert (hakuna data)
    _add_sessions(db_session, facility, patient, [("routine", None)])
    resp = client.get(f"/api/v1/facilities/{facility.id}/analytics/triage-accuracy?days=30")
    data = resp.json()
    assert data["total_reviewed"] == 0
    assert data["alert"] is False
