"""Tests za feedback loop ya clinician — endpoint, validation, propagation."""
from app.models.scheduling import Appointment, QueueEntry, QueueStatus
from app.models.triage import TriageSession


def _join_queue(client, facility, patient):
    resp = client.post(
        f"/api/v1/facilities/{facility.id}/queue",
        json={"patient_id": patient.id, "is_walk_in": True},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def test_clinician_urgency_recorded(client, facility, patient, db_session):
    entry_id = _join_queue(client, facility, patient)
    resp = client.post(
        f"/api/v1/queue/{entry_id}/clinician-urgency",
        json={"clinician_urgency": "urgent"},
    )
    assert resp.status_code == 200
    assert resp.json()["clinician_urgency"] == "urgent"

    entry = db_session.get(QueueEntry, entry_id)
    assert entry.clinician_urgency == "urgent"


def test_clinician_urgency_propagates_to_triage_session(client, facility, patient, db_session):
    # Triage session + appointment + queue entry iliyounganishwa
    session_row = TriageSession(
        patient_id=patient.id,
        facility_id=facility.id,
        answers={},
        urgency="routine",
        outcome="slot_booked",
    )
    db_session.add(session_row)
    db_session.commit()

    slot = db_session.query(
        __import__("app.models.scheduling", fromlist=["Slot"]).Slot
    ).first()
    if slot is None:
        from datetime import date, datetime, time, timedelta

        from app.models.scheduling import Slot

        day = date.today() + timedelta(days=1)
        slot = Slot(
            facility_id=facility.id,
            date=day,
            start_time=time(9, 0),
            end_time=time(9, 30),
            capacity=2,
            booked=0,
        )
        db_session.add(slot)
        db_session.commit()

    appointment = Appointment(
        patient_id=patient.id,
        slot_id=slot.id,
        triage_session_id=session_row.id,
        status="booked",
    )
    db_session.add(appointment)
    db_session.commit()

    entry = QueueEntry(
        facility_id=facility.id,
        patient_id=patient.id,
        appointment_id=appointment.id,
        status=QueueStatus.WAITING.value,
    )
    db_session.add(entry)
    db_session.commit()

    resp = client.post(
        f"/api/v1/queue/{entry.id}/clinician-urgency",
        json={"clinician_urgency": "urgent"},
    )
    assert resp.status_code == 200

    db_session.refresh(session_row)
    assert session_row.clinician_urgency == "urgent"


def test_clinician_urgency_invalid_value_rejected(client, facility, patient):
    entry_id = _join_queue(client, facility, patient)
    resp = client.post(
        f"/api/v1/queue/{entry_id}/clinician-urgency",
        json={"clinician_urgency": "hackerman"},
    )
    assert resp.status_code == 422


def test_clinician_urgency_unknown_entry_404(client, facility):
    resp = client.post(
        f"/api/v1/queue/99999/clinician-urgency",
        json={"clinician_urgency": "urgent"},
    )
    assert resp.status_code == 404
