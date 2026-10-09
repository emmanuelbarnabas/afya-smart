"""SMS reminders — kumbusho la miadi (siku kabla, dedup kwa reminder_sent_at).

Runner inaitwa na endpoint ya admin (`POST /api/v1/reminders/run`) au cron.
Bila AT credentials, SMS inalogiwa tu (dev mode — angalia services/notify.py).
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.patient import Patient
from app.models.scheduling import Appointment, AppointmentStatus, Slot
from app.services.notify import send_sms

logger = logging.getLogger("afyasmart.reminders")

REMINDER_LEAD_HOURS = 24  # tuma ~siku moja kabla


def due_appointments(db: Session, now: datetime | None = None) -> list[tuple[Appointment, Slot, Patient]]:
    """Miadi yenye kumbusho inayopasa: ndani ya masaa 24, BOOKED, haijatumwa."""
    now = now or datetime.now().astimezone()
    horizon = now + timedelta(hours=REMINDER_LEAD_HOURS)

    rows = db.execute(
        select(Appointment, Slot, Patient)
        .join(Slot, Appointment.slot_id == Slot.id)
        .join(Patient, Appointment.patient_id == Patient.id)
        .where(
            Appointment.status == AppointmentStatus.BOOKED.value,
            Appointment.reminder_sent_at.is_(None),
            Slot.date >= now.date(),
            Slot.date <= horizon.date(),
        )
        .order_by(Slot.date.asc(), Slot.start_time.asc())
    ).all()

    due: list[tuple[Appointment, Slot, Patient]] = []
    for appointment, slot, patient in rows:
        start = datetime.combine(slot.date, slot.start_time).astimezone()
        if start <= now or start > horizon:
            continue  # imepita, au iko mbali zaidi ya dirisha la masaa 24
        due.append((appointment, slot, patient))
    return due


def send_due_reminders(db: Session, now: datetime | None = None) -> dict:
    """Tuma kumbusho zote zinazopasa; rudisha ripoti (kwa admin endpoint)."""
    now = now or datetime.now().astimezone()
    sent, skipped = 0, 0
    for appointment, slot, patient in due_appointments(db, now):
        if not patient.phone_number:
            skipped += 1  # mgonjwa bila SIM — hakuna nambari ya kutumia
            continue
        start = datetime.combine(slot.date, slot.start_time)
        when_label = f"{start.strftime('%A %d/%m')} saa {start.strftime('%H:%M')}"
        message = (
            f"Afya Smart: Kumbusho — miadi yako ni {when_label}. "
            "Fika dakika 10 kabla. Kubadilisha: piga *384*37894#."
        )
        if send_sms(patient.phone_number, message):
            appointment.reminder_sent_at = now
            sent += 1
        else:
            skipped += 1
    db.commit()

    # Kwa siku zijazo (kama hakuna kwenye dirisha la 24h): ripoti ya kutosha
    return {"sent": sent, "skipped": skipped, "checked_at": now.isoformat()}

