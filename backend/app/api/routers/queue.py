"""Queue endpoints — dashboard ya front-desk: foleni, call-next, bypass ya dharura."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.scheduling import QueueStatus
from app.schemas.scheduling import CallNextResult, QueueEntryOut, QueueJoinRequest
from app.services import queue as queue_service

router = APIRouter(tags=["queue"])


@router.get("/facilities/{facility_id}/queue", response_model=list[QueueEntryOut])
def get_queue(facility_id: int, db: Session = Depends(get_db)):
    """Foleni inayosubiri, imepangwa kwa priority (dharura kwanza) kisha muda."""
    return queue_service.waiting_entries(db, facility_id)


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
    return entry


@router.post("/facilities/{facility_id}/queue/call-next", response_model=CallNextResult)
def call_next(facility_id: int, db: Session = Depends(get_db)):
    """Kitufe cha 'Call next patient' cha front-desk."""
    entry = queue_service.call_next(db, facility_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Foleni ni tupu")
    return CallNextResult(
        entry=QueueEntryOut.model_validate(entry),
        waiting_count=queue_service.waiting_count(db, facility_id),
    )


@router.post("/queue/{entry_id}/status", response_model=QueueEntryOut)
def update_status(entry_id: int, status: QueueStatus, db: Session = Depends(get_db)):
    """Badilisha hali: in_consult, done, left."""
    entry = queue_service.mark_status(db, entry_id, status)
    if entry is None:
        raise HTTPException(status_code=404, detail="Queue entry haipo")
    return entry


@router.get("/facilities/{facility_id}/queue/count")
def queue_count(facility_id: int, db: Session = Depends(get_db)):
    return {"facility_id": facility_id, "waiting": queue_service.waiting_count(db, facility_id)}
