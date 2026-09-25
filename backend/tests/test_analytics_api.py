"""Tests za analytics API — demand, forecast, queue summary, triage outcomes."""
from datetime import datetime, timezone

from app.models.scheduling import QueueEntry, QueueStatus
from app.models.triage import TriageSession


def test_demand_returns_points(client, facility, patient, db_session):
    db_session.add(
        QueueEntry(
            facility_id=facility.id,
            patient_id=patient.id,
            joined_at=datetime(2026, 9, 22, 7, 30, tzinfo=timezone.utc),
        )
    )
    db_session.commit()

    resp = client.get(f"/api/v1/facilities/{facility.id}/analytics/demand?days=7")
    assert resp.status_code == 200
    points = resp.json()
    assert len(points) >= 1
    assert points[0]["hour"] == 7
    assert points[0]["visits"] >= 1


def test_demand_forecast_returns_24_hours(client, facility):
    resp = client.get(f"/api/v1/facilities/{facility.id}/analytics/demand-forecast")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 24
    # Peak ya asubuhi (6-9) ina demand kubwa kuliko saa 15 bila history
    by_hour = {d["hour"]: d["expected_visits"] for d in data}
    assert by_hour[7] > by_hour[15]


def test_queue_summary_counts(client, facility, patient, db_session):
    db_session.add_all(
        [
            QueueEntry(facility_id=facility.id, patient_id=patient.id, status=QueueStatus.WAITING.value),
            QueueEntry(facility_id=facility.id, patient_id=patient.id, status=QueueStatus.CALLED.value),
            QueueEntry(
                facility_id=facility.id,
                patient_id=patient.id,
                status=QueueStatus.DONE.value,
                completed_at=datetime.now(timezone.utc),
            ),
            QueueEntry(
                facility_id=facility.id,
                patient_id=patient.id,
                is_emergency_bypass=True,
            ),
        ]
    )
    db_session.commit()

    resp = client.get(f"/api/v1/facilities/{facility.id}/analytics/queue-summary")
    data = resp.json()
    assert data["waiting"] == 1
    assert data["called"] == 1
    assert data["done_today"] == 1
    assert data["emergency_bypasses_today"] == 1


def test_triage_outcomes(client, facility, patient, db_session):
    db_session.add_all(
        [
            TriageSession(
                patient_id=patient.id,
                facility_id=facility.id,
                answers={},
                urgency="emergency",
                outcome="emergency_directed",
            ),
            TriageSession(
                patient_id=patient.id,
                facility_id=facility.id,
                answers={},
                urgency="self_care",
                outcome="self_care_given",
            ),
            TriageSession(
                patient_id=patient.id,
                facility_id=facility.id,
                answers={},
                urgency="routine",
                outcome=None,  # abandoned
            ),
        ]
    )
    db_session.commit()

    resp = client.get(f"/api/v1/facilities/{facility.id}/analytics/triage-outcomes")
    data = resp.json()
    assert data["emergency_directed"] == 1
    assert data["self_care_given"] == 1
    assert data["abandoned"] == 1
    assert data["total"] == 3
