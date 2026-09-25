"""Facility + slots + booking endpoints (dashboard na API ya nje)."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.facility import Facility
from app.models.scheduling import Slot
from app.schemas.scheduling import BookingCreate, BookingOut, SlotOut
from app.services import booking as booking_service
from app.services import forecast

router = APIRouter(tags=["slots"])


@router.get("/facilities")
def list_facilities(db: Session = Depends(get_db)):
    facilities = db.scalars(select(Facility).order_by(Facility.name)).all()
    return [
        {
            "id": f.id,
            "name": f.name,
            "code": f.code,
            "level": f.level,
            "region": f.region,
            "district": f.district,
            "opens_at": f.opens_at.isoformat() if f.opens_at else None,
            "closes_at": f.closes_at.isoformat() if f.closes_at else None,
        }
        for f in facilities
    ]


@router.get("/facilities/{facility_id}/slots", response_model=list[SlotOut])
def list_slots(
    facility_id: int,
    day: date | None = Query(default=None, alias="date"),
    available_only: bool = Query(default=True),
    db: Session = Depends(get_db),
):
    """Rudisha slots za siku; kwa default available tu, pamoja na expected wait."""
    day = day or date.today()
    if available_only:
        slots = booking_service.available_slots(db, facility_id, day)
    else:
        slots = booking_service.all_slots(db, facility_id, day)
    if not slots:
        return []
    forecast.update_slot_forecasts(db, facility_id, day)
    for slot in slots:
        db.refresh(slot)
    return slots


@router.post("/bookings", response_model=BookingOut, status_code=201)
def create_booking(payload: BookingCreate, db: Session = Depends(get_db)):
    try:
        appointment = booking_service.book_slot(
            db,
            patient_id=payload.patient_id,
            slot_id=payload.slot_id,
            triage_session_id=payload.triage_session_id,
        )
    except booking_service.SlotNotFoundError:
        raise HTTPException(status_code=404, detail="Slot haipo")
    except booking_service.SlotFullError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return appointment


@router.delete("/bookings/{appointment_id}", response_model=BookingOut)
def cancel_booking(appointment_id: int, db: Session = Depends(get_db)):
    appointment = booking_service.cancel_booking(db, appointment_id)
    if appointment is None:
        raise HTTPException(status_code=404, detail="Booking haipo au haipo tena")
    return appointment
