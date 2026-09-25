"""Tests za queue API — join, call-next, priority, status transitions."""
from datetime import datetime, timezone

from app.models.scheduling import QueueEntry, QueueStatus


def _join(client, facility_id, patient_id, **kwargs):
    payload = {"patient_id": patient_id}
    payload.update(kwargs)
    return client.post(f"/api/v1/facilities/{facility_id}/queue", json=payload)


def test_join_queue_walk_in(client, facility, patient):
    resp = _join(client, facility.id, patient.id, is_walk_in=True)
    assert resp.status_code == 201
    assert resp.json()["status"] == "waiting"
    assert resp.json()["is_walk_in"] is True


def test_join_queue_emergency_bypass_gets_top_priority(client, facility, patient):
    resp = _join(client, facility.id, patient.id, is_emergency_bypass=True)
    assert resp.json()["priority"] == 100


def test_queue_ordered_by_priority_then_time(client, facility, patient, db_session):
    # Mgonjwa wa kawaida anayefika kwanza
    e1 = QueueEntry(facility_id=facility.id, patient_id=patient.id, priority=0)
    db_session.add(e1)
    db_session.flush()
    # Mgonjwa wa dharura anayefika baadaye
    e2 = QueueEntry(facility_id=facility.id, patient_id=patient.id, priority=100, is_emergency_bypass=True)
    db_session.add(e2)
    db_session.commit()

    resp = client.get(f"/api/v1/facilities/{facility.id}/queue")
    entries = resp.json()
    assert entries[0]["id"] == e2.id  # dharura kwanza
    assert entries[1]["id"] == e1.id


def test_call_next_returns_highest_priority(client, facility, patient, db_session):
    e1 = QueueEntry(facility_id=facility.id, patient_id=patient.id, priority=0)
    e2 = QueueEntry(facility_id=facility.id, patient_id=patient.id, priority=10)
    db_session.add_all([e1, e2])
    db_session.commit()

    resp = client.post(f"/api/v1/facilities/{facility.id}/queue/call-next")
    assert resp.status_code == 200
    data = resp.json()
    assert data["entry"]["id"] == e2.id
    assert data["entry"]["status"] == "called"
    assert data["waiting_count"] == 1


def test_call_next_empty_queue(client, facility):
    resp = client.post(f"/api/v1/facilities/{facility.id}/queue/call-next")
    assert resp.status_code == 404


def test_status_transitions(client, facility, patient, db_session):
    entry = QueueEntry(facility_id=facility.id, patient_id=patient.id)
    db_session.add(entry)
    db_session.commit()

    # in_consult
    resp = client.post(f"/api/v1/queue/{entry.id}/status?status=in_consult")
    assert resp.json()["status"] == "in_consult"

    # done — completed_at inawekwa
    resp = client.post(f"/api/v1/queue/{entry.id}/status?status=done")
    assert resp.json()["status"] == "done"
    assert resp.json()["completed_at"] is not None


def test_status_invalid_entry(client, facility):
    resp = client.post(f"/api/v1/queue/99999/status?status=done")
    assert resp.status_code == 404


def test_queue_count(client, facility, patient, db_session):
    db_session.add(QueueEntry(facility_id=facility.id, patient_id=patient.id))
    db_session.add(QueueEntry(facility_id=facility.id, patient_id=patient.id))
    db_session.commit()

    resp = client.get(f"/api/v1/facilities/{facility.id}/queue/count")
    assert resp.json()["waiting"] == 2
