"""Booking service — slot availability, booking with capacity check, cancel.

Uhalisia: mgonjwa hawezi kuboek slot iliyopita (start_time iliyofya) na kama
slots za leo zimejaa, mtiririko wa USSD unarudisha slots za KESHO.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.scheduling import Appointment, AppointmentStatus, Slot


class SlotFullError(Exception):
    pass


class SlotNotFoundError(Exception):
    pass


def _now_tz() -> datetime:
    """Saa za eneo la seva (Tanzania = EAT, UTC+3; hakuna DST).

    Slots zinahifadhiwa kama saa za ENEO (wall-clock), hivyo kulinganisha
    kunafaa kufanyika kwa saa za eneo vile vile — si UTC (kosa la kawaida:
    slot za asubuhi za EAT zinaonekana 'future' kwa UTC kwa masaa 3).
    """
    return datetime.now().astimezone()


def _slot_start_dt(slot: Slot) -> datetime:
    """Slot start kama aware datetime kwa saa za eneo."""
    return datetime.combine(slot.date, slot.start_time).astimezone()


def available_slots(db: Session, facility_id: int, day: date) -> list[Slot]:
    """Slots za siku iliyotolewa zenye nafasi (booked < capacity).

    Kama siku ni LEO, slots zilizopita (start_time < now) hazionekani —
    mgonjwa hawezi kubook miadi iliyopita.
    """
    stmt = (
        select(Slot)
        .where(Slot.facility_id == facility_id, Slot.date == day)
        .order_by(Slot.start_time.asc())
    )
    slots = [s for s in db.scalars(stmt) if s.booked < s.capacity]
    if day == date.today():
        now = _now_tz()
        slots = [s for s in slots if _slot_start_dt(s) > now]
    return slots


def all_slots(db: Session, facility_id: int, day: date) -> list[Slot]:
    stmt = (
        select(Slot)
        .where(Slot.facility_id == facility_id, Slot.date == day)
        .order_by(Slot.start_time.asc())
    )
    return list(db.scalars(stmt))


def book_slot(
    db: Session,
    patient_id: int,
    slot_id: int,
    triage_session_id: int | None = None,
) -> Appointment:
    """Book slot — inahakikisha capacity, double-booking, na kuwa slot iko njiani."""
    slot = db.get(Slot, slot_id)
    if slot is None:
        raise SlotNotFoundError(f"Slot {slot_id} haipo")

    if slot.booked >= slot.capacity:
        raise SlotFullError(f"Slot {slot_id} imejaa")

    # Zuia mgonjwa ku-book slot iliyopita (race: menu ilionyesha, muda umefika)
    if _slot_start_dt(slot) <= _now_tz():
        raise SlotFullError("Slot hii imepita — chagua muda mwingine")

    # Zuia mgonjwa kuwa na miadi miili isiyohitajika siku moja
    existing = db.scalar(
        select(Appointment)
        .join(Slot, Appointment.slot_id == Slot.id)
        .where(
            Appointment.patient_id == patient_id,
            Slot.date == slot.date,
            Appointment.status == AppointmentStatus.BOOKED.value,
        )
    )
    if existing is not None:
        raise SlotFullError("Mgonjwa anayo miadi tayari siku hiyo")

    appointment = Appointment(
        patient_id=patient_id,
        slot_id=slot_id,
        triage_session_id=triage_session_id,
        status=AppointmentStatus.BOOKED.value,
    )
    slot.booked += 1
    db.add(appointment)
    db.commit()
    db.refresh(appointment)
    return appointment


def cancel_booking(db: Session, appointment_id: int) -> Appointment | None:
    """Ghairi miadi na punguza booked count ya slot."""
    appointment = db.get(Appointment, appointment_id)
    if appointment is None or appointment.status != AppointmentStatus.BOOKED.value:
        return None
    appointment.status = AppointmentStatus.CANCELLED.value
    slot = db.get(Slot, appointment.slot_id)
    if slot is not None and slot.booked > 0:
        slot.booked -= 1
    db.commit()
    db.refresh(appointment)
    return appointment
