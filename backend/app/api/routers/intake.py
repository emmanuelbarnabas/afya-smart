"""Intake router — the registration channel for patients without a SIM.

Africa's Talking is a bridge between the patient's phone and the backend; it
never holds the platform's intelligence. A patient who has no SIM (no phone
number) cannot be discovered through USSD/SMS, so intake is the explicit
registration channel that brings them into the *same* backend, queue, and
dashboard as the USSD patient.

Flow:
    POST /intake            → create a patient record (name/details, no phone)
    POST /intake/{id}/queue → join the shared queue at the home facility

This guarantees one backend, one database, one queue: no duplicate facility
system, no separate triage engine, nothing to reconcile later.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.facility import Facility
from app.models.patient import Patient
from app.models.scheduling import QueueStatus
from app.schemas.patient import IntakeCreate, PatientOut
from app.services import intake as intake_service
from app.services import queue as queue_service

router = APIRouter(tags=["intake"], prefix="/api/v1/intake")


def _get_facility_or_404(facility_id: int, db: Session) -> Facility:
    facility = db.get(Facility, facility_id)
    if facility is None:
        raise HTTPException(status_code=404, detail="Foleni haipo")
    return facility


@router.post("", response_model=PatientOut, status_code=201)
def create_intake(payload: IntakeCreate, db: Session = Depends(get_db)):
    """Register a phone-less patient (no SIM). Creates the record; joins the
    queue only after the caller posts to /intake/{id}/queue."""
    facility = None
    if payload.facility_id is not None:
        facility = _get_facility_or_404(payload.facility_id, db)

    patient = intake_service.get_or_create_patient(
        db,
        full_name=payload.full_name,
        phone_number=None,  # no SIM → no phone number
        preferred_language=payload.preferred_language,
        facility=facility,
        is_anonymous=True,
    )
    return PatientOut.model_validate(patient)


@router.post("/{patient_id}/queue", response_model=dict, status_code=201)
def intake_join_queue(patient_id: int, db: Session = Depends(get_db)):
    """Put a registered patient into the shared queue at their home facility.

    For a phone-less patient this is the intake/registration step that moves
    them from 'registered' to 'waiting in the queue'. A USSD patient reaches
    this queue through triage/booking instead, but it is the *same* queue the
    dashboard shows.
    """
    patient = db.get(Patient, patient_id)
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient haipo")

    if patient.is_anonymous and not patient.phone_number:
        pass  # phone-less patient is allowed to join queue

    if patient.facility_id is None:
        raise HTTPException(
            status_code=422,
            detail="Tafadhali binisha foleni (facility) kabla ya kuingia kwenye foleni.",
        )

    entry = queue_service.join_queue(
        db,
        facility_id=patient.facility_id,
        patient_id=patient.id,
        is_walk_in=True,
        is_emergency_bypass=False,
        priority=0,
    )
    return {
        "patient_id": patient.id,
        "patient_name": patient.full_name,
        "facility_id": patient.facility_id,
        "status": QueueStatus.WAITING.value,
        "queue_position": queue_service.position_of(db, entry),
    }


@router.get("/{patient_id}", response_model=PatientOut)
def get_intake(patient_id: int, db: Session = Depends(get_db)):
    """Read a registered patient (phone-less or not)."""
    patient = db.get(Patient, patient_id)
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient haipo")
    return PatientOut.model_validate(patient)
