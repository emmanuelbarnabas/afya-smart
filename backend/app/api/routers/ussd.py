"""USSD router — Africa's Talking callback na mtiririko wa triage + booking.

Africa's Talking inatuma POST ya application/x-www-form-urlencoded yenye:
    sessionId, serviceCode, phoneNumber, text

``text`` ni majibu yote ya session yaliyojitenganishwa na ``*``:
    "" → "1" → "1*1" → "1*1*0" ... (kila screen inaongeza jibu moja)
Jibu ni maandishi yaliyoanza na "CON " (endelea) au "END " (maliza).
"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Form, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.facility import Facility
from app.models.patient import Patient
from app.models.scheduling import QueueEntry, QueueStatus, Slot
from app.models.triage import TriageSession, UrgencyLevel
from app.services import booking as booking_service
from app.services import forecast, queue as queue_service
from app.services import triage as triage_service
from app.services.notify import notify_booking_confirmed

router = APIRouter(tags=["ussd"])

# ----------------------------------------------------------------------------
# Strings (i18n — Kiswahili na Kiingereza)
# ----------------------------------------------------------------------------
STRINGS: dict[str, dict[str, str]] = {
    "sw": {
        "welcome": "Karibu AFYA SMART\n1. Kiswahili\n2. English",
        "menu": "Chagua huduma:\n1. Kagua dalili zako\n2. Miadi/Ongeza muda\n3. Nafasi yangu kwenye foleni",
        "invalid": "Jibu si sahihi. Jaribu tena.",
        "slot_header": "Chagua muda wa miadi (leo):",
        "no_slots": "Samahani, hakuna nafasi zilizobaki leo. Jaribu tena kesho asubuhi.",
        "booked_ok": "Miadi imethibitishwa: {label}. Utapokelewa SMS.",
        "queue_status": "Nafasi yako: #{pos}. Wasilisha namba yako ukifika.",
        "queue_none": "Hujaingia kwenye foleni. Tumia menyu ya 1 kuanza.",
        "urgent_queued": "Hali yako ni ya haraka. Umewekwa foleni ya leo, nafasi #{pos}. Fika {facility} sasa.",
        "bye": "Asante kwa kutumia Afya Smart.",
    },
    "en": {
        "welcome": "Welcome to AFYA SMART\n1. Kiswahili\n2. English",
        "menu": "Choose a service:\n1. Check your symptoms\n2. Book an appointment\n3. My queue position",
        "invalid": "Invalid input. Try again.",
        "slot_header": "Choose an appointment time (today):",
        "no_slots": "Sorry, no slots left today. Try again tomorrow morning.",
        "booked_ok": "Appointment confirmed: {label}. You will receive an SMS.",
        "queue_status": "Your position: #{pos}. Show your number when you arrive.",
        "queue_none": "You are not in the queue. Use option 1 to start.",
        "urgent_queued": "Your case is urgent. You have been added to today's queue, position #{pos}. Go to {facility} now.",
        "bye": "Thank you for using Afya Smart.",
    },
}


def _t(lang: str, key: str, **kwargs) -> str:
    return STRINGS.get(lang, STRINGS["sw"])[key].format(**kwargs)


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
def get_or_create_patient(db: Session, phone_number: str) -> Patient:
    patient = db.scalar(select(Patient).where(Patient.phone_number == phone_number))
    if patient is None:
        patient = Patient(phone_number=phone_number, preferred_language="sw")
        db.add(patient)
        db.commit()
        db.refresh(patient)
    return patient


def get_default_facility(db: Session) -> Facility | None:
    return db.scalar(select(Facility).order_by(Facility.id).limit(1))


def current_triage_session(db: Session, at_session_id: str) -> TriageSession | None:
    return db.scalar(
        select(TriageSession)
        .where(TriageSession.at_session_id == at_session_id)
        .order_by(TriageSession.created_at.desc())
        .limit(1)
    )


def recommended_slots(db: Session, facility_id: int, day: date, limit: int = 3) -> list[Slot]:
    """Slots zenye expected wait fupi zaidi — inasukuma demand nje ya peak."""
    slots = booking_service.available_slots(db, facility_id, day)
    slots.sort(key=forecast.expected_wait_minutes)
    return slots[:limit]


def slot_label(slot: Slot) -> str:
    wait = slot.expected_wait_minutes or forecast.expected_wait_minutes(slot)
    return f"leo {slot.start_time.strftime('%H:%M')} (~{wait} min)"


def _render_slot_menu(db: Session, lang: str, facility: Facility) -> str:
    slots = recommended_slots(db, facility.id, date.today())
    if not slots:
        return f"END {_t(lang, 'no_slots')}"
    lines = [_t(lang, "slot_header")]
    for idx, slot in enumerate(slots, start=1):
        lines.append(f"{idx}. {slot_label(slot)}")
    return "CON " + "\n".join(lines)


def _book_chosen_slot(
    db: Session,
    lang: str,
    facility: Facility,
    patient: Patient,
    choice: str,
    triage_session_id: int | None,
    slots: list[Slot],
) -> str:
    try:
        idx = int(choice) - 1
        slot = slots[idx]
    except (ValueError, IndexError):
        return f"CON {_t(lang, 'invalid')}\n" + _render_slot_menu(db, lang, facility).removeprefix("CON ")

    forecast.update_slot_forecasts(db, facility.id, date.today())
    db.refresh(slot)
    try:
        appointment = booking_service.book_slot(
            db, patient_id=patient.id, slot_id=slot.id, triage_session_id=triage_session_id
        )
    except booking_service.SlotFullError:
        return _render_slot_menu(db, lang, facility)

    if triage_session_id is not None:
        session_row = db.get(TriageSession, triage_session_id)
        if session_row is not None:
            session_row.outcome = "slot_booked"
            db.commit()

    label = slot_label(slot)
    notify_booking_confirmed(patient.phone_number, label, facility.name)
    return f"END {_t(lang, 'booked_ok', label=label)}"


def _handle_triage_answer(
    db: Session,
    lang: str,
    levels: list[str],
    session_row: TriageSession,
    facility: Facility,
) -> str:
    # AT inaongeza jibu moja kwenye path kila screen; majibu yaliyohifadhiwa
    # ndiyo kiashirio halisi cha swali tunalotarajia (invalid input haihifadhiwi).
    q_index = len(session_row.answers or {})
    question = triage_service.TRIAGE_QUESTIONS[q_index]
    value = triage_service.parse_answer(question, levels[-1])
    if value is None:
        return f"CON {_t(lang, 'invalid')}\n{question['prompt']}"

    answers = dict(session_row.answers or {})
    answers[question["key"]] = value
    session_row.answers = answers
    db.commit()

    next_index = q_index + 1
    if next_index < len(triage_service.TRIAGE_QUESTIONS):
        return f"CON {triage_service.TRIAGE_QUESTIONS[next_index]['prompt']}"

    # Maswali yote yamejibiwa → classify (ML model halisi + safety override)
    urgency, confidence, model_version = triage_service.classify_full(session_row.answers)
    session_row.urgency = urgency.value
    session_row.confidence = confidence
    session_row.model_version = model_version

    if urgency == UrgencyLevel.ROUTINE:
        # outcome inawekwa "slot_booked" tu baada ya booking kweli
        db.commit()
        return _render_slot_menu(db, lang, facility)

    session_row.outcome = triage_service.outcome_for_urgency(urgency)
    db.commit()

    if urgency == UrgencyLevel.EMERGENCY:
        return f"END {triage_service.message_for_urgency(urgency)}"

    if urgency == UrgencyLevel.URGENT:
        entry = queue_service.join_queue(
            db,
            facility_id=facility.id,
            patient_id=session_row.patient_id,
            is_walk_in=True,
            priority=queue_service.urgency_priority(UrgencyLevel.URGENT),
        )
        pos = queue_service.position_of(db, entry)
        return f"END {_t(lang, 'urgent_queued', pos=pos, facility=facility.name)}"

    # SELF_CARE
    return f"END {triage_service.message_for_urgency(urgency)}"


def _handle_queue_position(db: Session, lang: str, phone_number: str) -> str:
    patient = get_or_create_patient(db, phone_number)
    entry = db.scalar(
        select(QueueEntry)
        .where(QueueEntry.patient_id == patient.id, QueueEntry.status == QueueStatus.WAITING.value)
        .order_by(QueueEntry.joined_at.desc())
    )
    if entry is None:
        return f"END {_t(lang, 'queue_none')}"
    pos = queue_service.position_of(db, entry)
    return f"END {_t(lang, 'queue_status', pos=pos)}"


# ----------------------------------------------------------------------------
# Routing ya screen kwa screen
# ----------------------------------------------------------------------------
def _route(db: Session, session_id: str, phone_number: str, levels: list[str]) -> str:
    # Screen 1: lugha
    if not levels:
        return f"CON {_t('sw', 'welcome')}"

    lang = "sw" if levels[0] == "1" else "en" if levels[0] == "2" else "sw"
    if len(levels) == 1:
        return _handle_language(levels, db, phone_number)

    facility = get_default_facility(db)
    if facility is None:
        return "END Huduma haipatikani kwa sasa. Jaribu tena baadaye."

    choice = levels[1]

    if choice == "1":  # triage
        session_row = current_triage_session(db, session_id)
        if session_row is None:
            patient = get_or_create_patient(db, phone_number)
            session_row = TriageSession(
                patient_id=patient.id,
                facility_id=facility.id,
                at_session_id=session_id,
                answers={},
                urgency=UrgencyLevel.ROUTINE.value,
            )
            db.add(session_row)
            db.commit()
            return f"CON {triage_service.TRIAGE_QUESTIONS[0]['prompt']}"

        # Kama maswali yote yamejibiwa → jibu hili ni slot choice (ROUTINE flow)
        if len(session_row.answers or {}) >= len(triage_service.TRIAGE_QUESTIONS):
            patient = get_or_create_patient(db, phone_number)
            slots = recommended_slots(db, facility.id, date.today())
            return _book_chosen_slot(
                db, lang, facility, patient, levels[-1], session_row.id, slots
            )
        return _handle_triage_answer(db, lang, levels, session_row, facility)

    if choice == "2":  # booking bila triage
        if len(levels) == 2:
            return _render_slot_menu(db, lang, facility)
        patient = get_or_create_patient(db, phone_number)
        slots = recommended_slots(db, facility.id, date.today())
        return _book_chosen_slot(db, lang, facility, patient, levels[2], None, slots)

    if choice == "3":  # nafasi kwenye foleni
        return _handle_queue_position(db, lang, phone_number)

    return f"CON {_t(lang, 'invalid')}\n{_t(lang, 'menu')}"


def _handle_language(levels: list[str], db: Session, phone_number: str) -> str:
    choice = levels[0]
    if choice not in ("1", "2"):
        return f"CON {_t('sw', 'welcome')}"
    lang = "sw" if choice == "1" else "en"
    patient = get_or_create_patient(db, phone_number)
    patient.preferred_language = lang
    db.commit()
    return f"CON {_t(lang, 'menu')}"


# ----------------------------------------------------------------------------
# Endpoint
# ----------------------------------------------------------------------------
@router.post("/ussd", response_class=PlainTextResponse)
def ussd_callback(
    db: Session = Depends(get_db),
    session_id: str = Form(..., alias="sessionId"),
    phone_number: str = Form(..., alias="phoneNumber"),
    text: str = Form(default=""),
    service_code: str = Form(default="", alias="serviceCode"),
):
    levels = text.split("*") if text else []
    try:
        response = _route(db, session_id, phone_number, levels)
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="USSD processing error")
    return response
