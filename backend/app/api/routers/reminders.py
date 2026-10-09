"""Reminders endpoints — kumbusho za miadi (admin/cron)."""
from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.patient import Patient
from app.models.scheduling import Appointment, AppointmentStatus, Slot
from app.services.reminders import due_appointments, send_due_reminders

router = APIRouter(prefix="/reminders", tags=["reminders"])


@router.get("/upcoming")
def upcoming_appointments(
    hours: int = Query(default=24, ge=1, le=168),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Miadi ijayo (kwa page ya Kumbusho): booked, ndani ya masaa `hours` zijazo."""
    now = datetime.now().astimezone()
    horizon = now + timedelta(hours=hours)

    rows = db.execute(
        select(Appointment, Slot, Patient)
        .join(Slot, Appointment.slot_id == Slot.id)
        .join(Patient, Appointment.patient_id == Patient.id)
        .where(
            Appointment.status == AppointmentStatus.BOOKED.value,
            Slot.date >= now.date(),
        )
        .order_by(Slot.date.asc(), Slot.start_time.asc())
        .limit(limit * 4)  # pre-filter; tunachuja kwa datetime kamili chini
    ).all()

    items: list[dict] = []
    for appointment, slot, patient in rows:
        start = datetime.combine(slot.date, slot.start_time).astimezone()
        if start < now or start > horizon:
            continue
        items.append(
            {
                "appointment_id": appointment.id,
                "patient_name": patient.full_name,
                "patient_phone": patient.phone_number,
                "date": slot.date.isoformat(),
                "start_time": slot.start_time.strftime("%H:%M"),
                "reminder_sent": appointment.reminder_sent_at is not None,
            }
        )
        if len(items) >= limit:
            break

    return {"hours": hours, "count": len(items), "items": items}


@router.post("/run")
def run_reminders(
    dry_run: bool = Query(default=False, description="Kuhesabu tu, bila kutuma"),
    db: Session = Depends(get_db),
):
    """Tuma kumbusho za miadi (masaa 24 zijazo). Dry run inarudisha hesabu tu."""
    # (dry_run inarudisha hesabu tu; bila dry_run inatuma SMS na kurekodi reminder_sent_at)
    if dry_run:
        due = due_appointments(db)
        return {"dry_run": True, "due": len(due)}
    return send_due_reminders(db)
