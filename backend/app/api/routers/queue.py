"""Queue endpoints — dashboard ya front-desk: foleni, call-next, bypass ya dharura."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.patient import Patient
from app.models.scheduling import Appointment, QueueEntry, QueueStatus
from app.models.triage import TriageSession, UrgencyLevel
from app.schemas.scheduling import (
    CallNextResult,
    ClinicianUrgencyIn,
    QueueEntryOut,
    QueueJoinRequest,
)
from app.services import queue as queue_service

router = APIRouter(tags=["queue"])


def _with_context(db: Session, entries: list[QueueEntry]) -> list[QueueEntryOut]:
    """Funga entries na context ya dashboard: jina la mgonjwa, muda wa kusubiri, nafasi."""
    patient_ids = {e.patient_id for e in entries}
    names: dict[int, str] = {}
    phones: dict[int, str] = {}
    if patient_ids:
        rows = db.execute(
            select(Patient.id, Patient.full_name, Patient.phone_number).where(
                Patient.id.in_(patient_ids)
            )
        ).all()
        for pid, full_name, phone in rows:
            names[pid] = full_name or None
            phones[pid] = phone

    waiting = [e for e in entries if e.status == QueueStatus.WAITING.value]
    positions = {e.id: i + 1 for i, e in enumerate(waiting)}

    # ETA hutumia mean service time moja kwa foleni yote (mtihani mmoja wa DB)
    eta_cache: dict[int, float] = {}

    out = []
    for e in entries:
        item = QueueEntryOut.model_validate(e)
        item.patient_name = names.get(e.patient_id)
        item.patient_phone = phones.get(e.patient_id)
        if e.joined_at is not None:
            item.waited_minutes = max(
                0, int((datetime.now(timezone.utc) - e.joined_at.replace(tzinfo=timezone.utc)).total_seconds() // 60)
            )
        item.position = positions.get(e.id)
        if e.status == QueueStatus.WAITING.value and item.position:
            per_patient = eta_cache.setdefault(
                e.facility_id,
                queue_service.mean_service_minutes(db, e.facility_id),
            )
            item.eta_minutes = max(
                0, int(round((item.position - 1) * per_patient + min(5.0, per_patient * 0.3)))
            )
        out.append(item)
    return out


@router.get("/facilities/{facility_id}/queue", response_model=list[QueueEntryOut])
def get_queue(facility_id: int, db: Session = Depends(get_db)):
    """Foleni inayosubiri, imepangwa kwa priority (dharura kwanza) kisha muda."""
    return _with_context(db, queue_service.waiting_entries(db, facility_id))


@router.post("/facilities/{facility_id}/queue", response_model=QueueEntryOut, status_code=201)
def join_queue(facility_id: int, payload: QueueJoinRequest, db: Session = Depends(get_db)):
    """Check-in: walk-in au appointment → queue entry."""
    entry = queue_service.join_queue(
        db,
        facility_id=facility_id,
        patient_id=payload.patient_id,
        appointment_id=payload.appointment_id,
        is_walk_in=payload.is_walk_in,
        is_emergency_bypass=payload.is_emergency_bypass,
        priority=payload.priority,
    )
    return _with_context(db, [entry])[0]


@router.post("/facilities/{facility_id}/queue/call-next", response_model=CallNextResult)
def call_next(facility_id: int, db: Session = Depends(get_db)):
    """Kitufe cha 'Call next patient' cha front-desk."""
    entry = queue_service.call_next(db, facility_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Foleni ni tupu")
    return CallNextResult(
        entry=_with_context(db, [entry])[0],
        waiting_count=queue_service.waiting_count(db, facility_id),
    )


@router.post("/queue/{entry_id}/status", response_model=QueueEntryOut)
def update_status(entry_id: int, status: QueueStatus, db: Session = Depends(get_db)):
    """Badilisha hali: in_consult, done, left."""
    entry = queue_service.mark_status(db, entry_id, status)
    if entry is None:
        raise HTTPException(status_code=404, detail="Queue entry haipo")
    return _with_context(db, [entry])[0]


@router.post("/queue/{entry_id}/clinician-urgency", response_model=QueueEntryOut)
def set_clinician_urgency(entry_id: int, payload: ClinicianUrgencyIn, db: Session = Depends(get_db)):
    """Feedback loop: hali ya mwisho ya mgonjwa kama clinician alivyoona.

    Inaunganisha na triage session ya mgonjwa (kama ipo) — hii ndiyo data
    inayopima usahihi wa triage (under-triage rate) na kufundisha model baadaye.
    """
    entry = db.get(QueueEntry, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Queue entry haipo")

    value = payload.clinician_urgency
    if value not in {u.value for u in UrgencyLevel}:
        raise HTTPException(status_code=422, detail="clinician_urgency si sahihi")

    entry.clinician_urgency = value

    # Propagate kwenye triage session ya sambamba (kama ipo)
    if entry.appointment_id is not None:
        appointment = db.get(Appointment, entry.appointment_id)
        if appointment is not None and appointment.triage_session_id is not None:
            session_row = db.get(TriageSession, appointment.triage_session_id)
            if session_row is not None:
                session_row.clinician_urgency = value
    db.commit()
    db.refresh(entry)
    return _with_context(db, [entry])[0]


@router.get("/facilities/{facility_id}/queue/count")
def queue_count(facility_id: int, db: Session = Depends(get_db)):
    return {"facility_id": facility_id, "waiting": queue_service.waiting_count(db, facility_id)}
