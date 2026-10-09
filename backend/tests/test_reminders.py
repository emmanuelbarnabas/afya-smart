"""Tests za SMS reminders — dirisha la masaa 24, dedup, dry run."""
from datetime import date, datetime, time, timedelta

from app.models.scheduling import Appointment, Slot


def _make_appointment(db_session, facility, patient, hours_ahead: float, reminded: bool = False):
    now = datetime.now()
    start = now + timedelta(hours=hours_ahead)
    slot = Slot(
        facility_id=facility.id,
        date=start.date(),
        start_time=start.time().replace(second=0, microsecond=0),
        end_time=(start + timedelta(minutes=30)).time().replace(second=0, microsecond=0),
        capacity=2,
        booked=1,
    )
    db_session.add(slot)
    db_session.flush()
    appointment = Appointment(
        patient_id=patient.id,
        slot_id=slot.id,
        status="booked",
        reminder_sent_at=datetime.now() if reminded else None,
    )
    db_session.add(appointment)
    db_session.commit()
    return appointment


def test_reminder_due_within_24h(client, facility, patient, db_session):
    _make_appointment(db_session, facility, patient, hours_ahead=5)
    resp = client.post("/api/v1/reminders/run?dry_run=true")
    assert resp.status_code == 200
    assert resp.json()["due"] >= 1


def test_reminder_skips_already_sent(client, facility, patient, db_session):
    _make_appointment(db_session, facility, patient, hours_ahead=5, reminded=True)
    resp = client.post("/api/v1/reminders/run?dry_run=true")
    assert resp.status_code == 200
    assert resp.json()["due"] == 0


def test_reminder_skips_far_future(client, facility, patient, db_session):
    _make_appointment(db_session, facility, patient, hours_ahead=48)
    resp = client.post("/api/v1/reminders/run?dry_run=true")
    assert resp.status_code == 200
    assert resp.json()["due"] == 0


def test_reminder_run_sends_and_marks(client, facility, patient, db_session):
    appointment = _make_appointment(db_session, facility, patient, hours_ahead=5)
    resp = client.post("/api/v1/reminders/run")
    assert resp.status_code == 200
    assert resp.json()["sent"] >= 1

    db_session.refresh(appointment)
    assert appointment.reminder_sent_at is not None


def test_reminder_run_is_idempotent(client, facility, patient, db_session):
    _make_appointment(db_session, facility, patient, hours_ahead=5)
    r1 = client.post("/api/v1/reminders/run")
    assert r1.json()["sent"] >= 1
    r2 = client.post("/api/v1/reminders/run")
    assert r2.json()["sent"] == 0  # dedup — hazijatumwa mara mbili
