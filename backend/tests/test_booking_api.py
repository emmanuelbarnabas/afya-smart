"""Tests za slots & booking API — capacity, double-booking, cancel."""
from datetime import date, datetime, timedelta

from app.models.scheduling import Appointment, Slot
from app.services.booking import SlotFullError


def _fixture_day() -> date:
    """Siku ile ile inayotumiwa na slots_today fixture (baada ya 7:30 → kesho)."""
    now = datetime.now()
    return now.date() if now.hour < 7 else now.date() + timedelta(days=1)


def test_list_available_slots(client, facility, slots_today):
    resp = client.get(f"/api/v1/facilities/{facility.id}/slots?date={_fixture_day().isoformat()}")
    assert resp.status_code == 200
    slots = resp.json()
    assert len(slots) == 5
    assert all(s["booked"] < s["capacity"] for s in slots)
    # expected wait imewekwa na forecast
    assert all(s["expected_wait_minutes"] is not None for s in slots)
    # Peak ya asubuhi ina wait ndefu kuliko mchana
    morning = next(s for s in slots if s["start_time"] == "08:00:00")
    afternoon = next(s for s in slots if s["start_time"] == "14:00:00")
    assert morning["expected_wait_minutes"] > afternoon["expected_wait_minutes"]


def test_past_slots_hidden_and_unbookable(client, facility, patient, db_session):
    """Slots za leo zilizopita hazionekani na haziwezi kubookiwa (uhalisia)."""
    from app.models.scheduling import Slot

    now = datetime.now()
    past_slot = Slot(
        facility_id=facility.id,
        date=now.date(),
        start_time=(now - timedelta(minutes=60)).time().replace(second=0, microsecond=0),
        end_time=(now - timedelta(minutes=30)).time().replace(second=0, microsecond=0),
        capacity=2,
        booked=0,
    )
    db_session.add(past_slot)
    db_session.commit()

    # Haionekani kwenye slots za leo
    resp = client.get(f"/api/v1/facilities/{facility.id}/slots")
    ids = [s["id"] for s in resp.json()]
    assert past_slot.id not in ids

    # Haiwezi kubookiwa
    resp = client.post("/api/v1/bookings", json={"patient_id": patient.id, "slot_id": past_slot.id})
    assert resp.status_code == 409


def test_booking_success(client, facility, patient, slots_today, db_session):
    slot = slots_today[0]
    resp = client.post(
        "/api/v1/bookings",
        json={"patient_id": patient.id, "slot_id": slot.id},
    )
    assert resp.status_code == 201
    assert resp.json()["status"] == "booked"
    db_session.refresh(slot)
    assert slot.booked == 1


def test_booking_capacity_full(client, facility, patient, slots_today, db_session):
    slot = slots_today[0]
    slot.booked = slot.capacity  # 2/2
    db_session.commit()

    resp = client.post("/api/v1/bookings", json={"patient_id": patient.id, "slot_id": slot.id})
    assert resp.status_code == 409


def test_double_booking_same_day_rejected(client, facility, patient, slots_today):
    s1, s2 = slots_today[0], slots_today[1]
    r1 = client.post("/api/v1/bookings", json={"patient_id": patient.id, "slot_id": s1.id})
    assert r1.status_code == 201
    r2 = client.post("/api/v1/bookings", json={"patient_id": patient.id, "slot_id": s2.id})
    assert r2.status_code == 409


def test_booking_unknown_slot(client, facility, patient):
    resp = client.post("/api/v1/bookings", json={"patient_id": patient.id, "slot_id": 99999})
    assert resp.status_code == 404


def test_cancel_booking_frees_capacity(client, facility, patient, slots_today, db_session):
    slot = slots_today[0]
    resp = client.post("/api/v1/bookings", json={"patient_id": patient.id, "slot_id": slot.id})
    appt_id = resp.json()["id"]

    resp = client.delete(f"/api/v1/bookings/{appt_id}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"
    db_session.refresh(slot)
    assert slot.booked == 0
