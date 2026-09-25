"""Queue endpoints — dashboard ya front-desk: foleni, call-next, bypass ya dharura."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.patient import Patient
from app.models.scheduling import QueueEntry, QueueStatus
from app.schemas.scheduling import CallNextResult, QueueEntryOut, QueueJoinRequest
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


@router.get("/facilities/{facility_id}/queue/count")
def queue_count(facility_id: int, db: Session = Depends(get_db)):
    return {"facility_id": facility_id, "waiting": queue_service.waiting_count(db, facility_id)}
