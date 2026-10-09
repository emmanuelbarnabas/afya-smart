"""
Seed script — creates a demo facility, generates today's slots, and a demo patient.

Run from backend/:
    .venv/bin/python -m app.seed
"""
import random

from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import func, select

from app.core.database import SessionLocal
from app.core.config import settings
from app.models import Facility, Patient, Slot
from app.models.scheduling import QueueEntry, QueueStatus
from app.models.triage import TriageSession

# ----------------------------------------------------------------------------
# Historia ya demo (siku 14) — inafanya analytics "zima": demand curve ya
# peak ya asubuhi, wait times halisi, na matokeo ya triage + feedback ya
# clinician. Hakuna history → dashboard anaonyesha chati tupu (demo dhaifu).
# ----------------------------------------------------------------------------
HISTORY_DAYS = 14


def seed_history(db, facility: Facility) -> None:
    """Tengeneza queue entries + triage sessions za siku ~14 zilizopita."""
    existing = db.scalar(
        select(func.count())
        .select_from(QueueEntry)
        .where(QueueEntry.facility_id == facility.id)
    ) or 0
    if existing >= 20:
        return  # history ipo tayari (au mfumo wa kweli una data) — usiingilie

    patients = list(db.scalars(select(Patient)).all())
    if not patients:
        patients = [
            Patient(phone_number="+255700000001", full_name="Demo Mgonjwa", preferred_language="sw")
        ]
        db.add_all(patients)
        db.flush()

    rng = random.Random(42)
    now = datetime.now(timezone.utc)

    # Saa za kuwasili na uzito wao (peak ya asubuhi 6–9 — tatizo la msingi)
    arrival_hours = list(range(6, 17))
    arrival_weights = [
        5, 7, 8,  # 6,7,8 — peak
        4, 3, 2, 2,  # 9,10,11,12
        2, 2, 2,  # 13,14,15
        1,
    ]

    urgency_pool = ["self_care"] * 3 + ["routine"] * 6 + ["urgent"] * 2 + ["emergency"]

    for day_offset in range(HISTORY_DAYS, 0, -1):
        day = (now - timedelta(days=day_offset)).date()
        n_visits = rng.randint(12, 22)
        for _ in range(n_visits):
            hour = rng.choices(arrival_hours, weights=arrival_weights, k=1)[0]
            minute = rng.randint(0, 59)
            joined = datetime(day.year, day.month, day.day, hour, minute, tzinfo=timezone.utc)
            # Subiri zaidi kwenye peak (6–9), chini nje ya peak — hii inapa
            # wait-times analytics mvuto wa kweli.
            peak_factor = 2.5 if hour < 9 else (1.2 if hour < 12 else 0.7)
            wait_min = max(2, int(rng.gauss(12 * peak_factor, 5)))
            called = joined + timedelta(minutes=wait_min)
            service_min = max(4, int(rng.gauss(14, 4)))
            completed = called + timedelta(minutes=service_min)
            if completed > now:
                continue

            patient = rng.choice(patients)
            is_urgent = rng.random() < 0.12
            entry = QueueEntry(
                facility_id=facility.id,
                patient_id=patient.id,
                is_walk_in=is_urgent,
                is_emergency_bypass=False,
                priority=10 if is_urgent else 0,
                status=QueueStatus.DONE.value,
                joined_at=joined,
                called_at=called,
                completed_at=completed,
            )
            db.add(entry)
            db.flush()  # entry.id kwa triage link

            # Triage session ya sambamba (~70% ya wagonjwa walitumia USSD triage)
            if rng.random() < 0.7:
                urgency = rng.choice(urgency_pool)
                # Feedback ya clinician: 85% inakubaliana, 10% over-triage,
                # 5% under-triage (ndiyo kipimo tunachotaka kifuate sifuri)
                roll = rng.random()
                if roll < 0.85:
                    clinician = urgency
                elif roll < 0.95:
                    clinician = _one_level_up(urgency)
                else:
                    clinician = _one_level_down(urgency)
                outcome = {
                    "emergency": "emergency_directed",
                    "urgent": "walk_in_directed",
                    "routine": "slot_booked",
                    "self_care": "self_care_given",
                }[urgency]
                db.add(
                    TriageSession(
                        patient_id=patient.id,
                        facility_id=facility.id,
                        at_session_id=f"seed-{day.isoformat()}-{entry.id}",
                        answers={},
                        urgency=urgency,
                        confidence=round(rng.uniform(0.55, 0.95), 2),
                        model_version="ml-v2",
                        outcome=outcome,
                        clinician_urgency=clinician,
                        created_at=joined,
                    )
                )


def _one_level_up(urgency: str) -> str:
    order = ["self_care", "routine", "urgent", "emergency"]
    idx = min(len(order) - 1, order.index(urgency) + 1)
    return order[idx]


def _one_level_down(urgency: str) -> str:
    order = ["self_care", "routine", "urgent", "emergency"]
    idx = max(0, order.index(urgency) - 1)
    return order[idx]


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


def generate_today_slots(db, facility: Facility, days: int = 1) -> None:
    """Tengeneza slots za siku `days` zijazo (leo + nyingine days-1).

    Kituo halisi kina ratiba ya siku zijazo — bila hii, booking ya kesho
    haipo na USSD inaisha kwa "hakuna nafasi" mara slots za leo zikijaa
    au kupita.
    """
    start_time = facility.opens_at or time(8, 0)
    end_time = facility.closes_at or time(17, 0)
    slot_minutes = 30

    for offset in range(days):
        day = date.today() + timedelta(days=offset)
        existing = db.scalar(select(Slot).where(Slot.facility_id == facility.id, Slot.date == day))
        if existing is not None:
            continue  # slots za siku hii zinazo

        # Busier in the morning peak (6-9 AM pattern from the proposal) → smaller capacity early
        t = datetime.combine(day, start_time)
        end_dt = datetime.combine(day, end_time)
        new_slots = []
        while t + timedelta(minutes=slot_minutes) <= end_dt:
            morning_peak = t.hour < 9
            new_slots.append(
                Slot(
                    facility_id=facility.id,
                    date=day,
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


def ensure_demo_intake_patient(db) -> Patient:
    """Phone-less demo patient — the 'no SIM' case that exercises intake.

    One anonymous patient is always available so the dashboard can display a
    no-SIM patient, join the shared queue, and be served like any other.
    """
    existing = db.scalar(
        select(Patient).where(Patient.full_name == "Demo Mgonjwa (no SIM)")
    )
    if existing is not None:
        return existing
    patient = Patient(
        full_name="Demo Mgonjwa (no SIM)",
        preferred_language="sw",
        is_anonymous=True,
    )
    db.add(patient)
    db.flush()
    return patient

def main() -> None:
    db = SessionLocal()
    try:
        facility = ensure_demo_facility(db)
        generate_today_slots(db, facility, days=7)
        ensure_demo_patient(db)
        ensure_demo_intake_patient(db)
        seed_history(db, facility)
        db.commit()
        print(f"Seed OK — facility '{facility.name}' ({facility.code}), env={settings.environment}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
