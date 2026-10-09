"""Tests za GET /reminders/upcoming — orodha ya miadi ijayo (page ya Kumbusho)."""
from datetime import datetime, timedelta

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


def test_upcoming_returns_soon_appointments(client, facility, patient, db_session):
    _make_appointment(db_session, facility, patient, hours_ahead=5)
    _make_appointment(db_session, facility, patient, hours_ahead=48)  # mbali — haipaswi

    resp = client.get("/api/v1/reminders/upcoming?hours=24")
    assert resp.status_code == 200
    data = resp.json()
    assert data["hours"] == 24
    assert data["count"] == 1
    item = data["items"][0]
    assert item["patient_phone"] == patient.phone_number
    assert item["reminder_sent"] is False
    assert "T" in item["date"] or "-" in item["date"]  # ISO date


def test_upcoming_marks_reminder_sent(client, facility, patient, db_session):
    _make_appointment(db_session, facility, patient, hours_ahead=5, reminded=True)
    resp = client.get("/api/v1/reminders/upcoming?hours=24")
    data = resp.json()
    assert data["count"] == 1
    assert data["items"][0]["reminder_sent"] is True


def test_upcoming_skips_past_and_far_future(client, facility, patient, db_session):
    _make_appointment(db_session, facility, patient, hours_ahead=-2)  # iliyopita
    _make_appointment(db_session, facility, patient, hours_ahead=72)  # mbali
    resp = client.get("/api/v1/reminders/upcoming?hours=24")
    assert resp.status_code == 200
    assert resp.json()["count"] == 0


def test_upcoming_respects_limit(client, facility, patient, db_session):
    for i in range(3):
        _make_appointment(db_session, facility, patient, hours_ahead=2 + i)
    resp = client.get("/api/v1/reminders/upcoming?hours=24&limit=2")
    assert resp.status_code == 200
    assert resp.json()["count"] == 2
