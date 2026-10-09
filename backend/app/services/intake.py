"""Intake service — register a patient without a phone number so they enter the
single backend, single queue, and single dashboard.

USSD/SMS find a patient by `phone_number`. A patient who has no SIM (no phone)
cannot be looked up that way, so intake creates the record from name + details,
assigns a home facility, and returns a `patient_id`. That `patient_id` is then
used by the queue endpoint to join the shared queue — the same queue the USSD
patient enters. One backend, one DB, one queue.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.facility import Facility
from app.models.patient import Patient
from app.models.scheduling import QueueEntry, QueueStatus


def get_or_create_patient(
    db: Session,
    *,
    full_name: str,
    phone_number: str | None = None,
    preferred_language: str = "sw",
    facility: Facility | None = None,
    facility_id: int | None = None,
    is_anonymous: bool = False,
) -> Patient:
    """Get an existing patient by phone if given; otherwise create a new one.

    Only `phone_number` (or none) is used to disambiguate. When no phone is
    supplied the patient is anonymous: created from name/details alone and
    eligible to join the queue the same way a USSD patient is.
    """
    patient: Patient | None = None
    if phone_number:
        patient = db.scalar(
            select(Patient).where(Patient.phone_number == phone_number)
        )

    if patient is None:
        patient = Patient(
            phone_number=phone_number,
            full_name=full_name,
            preferred_language=preferred_language,
            is_anonymous=is_anonymous,
        )
        if facility is not None:
            patient.facility_id = facility.id
        elif facility_id is not None:
            patient.facility_id = facility_id
        db.add(patient)
        db.flush()  # ensure id exists for queue join below
        db.commit()
        db.refresh(patient)
    return patient


def join_queue_with_intake(
    db: Session,
    *,
    full_name: str,
    phone_number: str | None = None,
    preferred_language: str = "sw",
    facility_id: int,
    is_walk_in: bool = True,
    is_emergency_bypass: bool = False,
) -> QueueEntry:
    """Register an intake patient and immediately join their home facility queue.

    This is the single entry point that unifies USSD, dashboard, and phone-less
    intake: one `patient_id`, one queue entry, one shared database.
    """
    patient = get_or_create_patient(
        db,
        full_name=full_name,
        phone_number=phone_number,
        preferred_language=preferred_language,
        facility_id=facility_id,
        is_anonymous=True,
    )
    entry = QueueEntry(
        facility_id=facility_id,
        patient_id=patient.id,
        is_walk_in=is_walk_in,
        is_emergency_bypass=is_emergency_bypass,
        priority=0,
        status=QueueStatus.WAITING.value,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry
