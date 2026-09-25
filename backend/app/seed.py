"""
Seed script — creates a demo facility, generates today's slots, and a demo patient.

Run from backend/:
    .venv/bin/python -m app.seed
"""
from datetime import date, datetime, time, timedelta

from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.config import settings
from app.models import Facility, Patient, Slot


def ensure_demo_facility(db) -> Facility:
    facility = db.scalar(select(Facility).where(Facility.code == "DSM-001"))
    if facility is None:
        facility = Facility(
            name="Afya Smart Demo Dispensary",
            code="DSM-001",
            level="dispensary",
            region="Dar es Salaam",
            district="Ilala",
        )
        db.add(facility)
        db.flush()
    return facility


def generate_today_slots(db, facility: Facility) -> None:
    today = date.today()
    existing = db.scalar(select(Slot).where(Slot.facility_id == facility.id, Slot.date == today))
    if existing is not None:
        return  # slots already generated

    # Half-hour slots from opening to closing time
    start = facility.opens_at or time(8, 0)
    end = facility.closes_at or time(17, 0)
    slot_minutes = 30

    # Busier in the morning peak (6-9 AM pattern from the proposal) → smaller capacity early
    t = datetime.combine(today, start)
    end_dt = datetime.combine(today, end)
    new_slots = []
    while t + timedelta(minutes=slot_minutes) <= end_dt:
        morning_peak = t.hour < 9
        new_slots.append(
            Slot(
                facility_id=facility.id,
                date=today,
                start_time=t.time(),
                end_time=(t + timedelta(minutes=slot_minutes)).time(),
                capacity=6 if morning_peak else 4,
                booked=0,
            )
        )
        t += timedelta(minutes=slot_minutes)
    db.add_all(new_slots)


def ensure_demo_patient(db) -> None:
    if db.scalar(select(Patient).where(Patient.phone_number == "+255700000001")) is None:
        db.add(Patient(phone_number="+255700000001", full_name="Demo Mgonjwa", preferred_language="sw"))


def main() -> None:
    db = SessionLocal()
    try:
        facility = ensure_demo_facility(db)
        generate_today_slots(db, facility)
        ensure_demo_patient(db)
        db.commit()
        print(f"Seed OK — facility '{facility.name}' ({facility.code}), env={settings.environment}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
