"""USSD router — Africa's Talking callback na mtiririko wa triage + booking.

Africa's Talking inatuma POST ya application/x-www-form-urlencoded yenye:
    sessionId, serviceCode, phoneNumber, text

``text`` ni majibu yote ya session yaliyojitenganishwa na ``*``:
    "" → "1" → "1*1" → "1*1*0" ... (kila screen inaongeza jibu moja)
Jibu ni maandishi yaliyoanza na "CON " (endelea) au "END " (maliza).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, Form, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.facility import Facility
from app.models.patient import Patient
from app.models.scheduling import (
    Appointment,
    AppointmentStatus,
    QueueEntry,
    QueueStatus,
    Slot,
)
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
        "menu": (
            "Chagua huduma:\n"
            "1. Kagua dalili zako\n"
            "2. Miadi/Ongeza muda\n"
            "3. Nafasi yangu kwenye foleni\n"
            "4. Tafuta hospitali\n"
            "5. Mwongozo wa afya\n"
            "6. Angalia miadi yangu\n"
            "0. Toka"
        ),
        "invalid": "Jibu si sahihi. Jaribu tena.",
        "region_header": "CHAGUA ENEO:",
        "facility_header": "CHAGUA HOSPITALI ({region}):",
        "facility_menu": (
            "{name}\n"
            "1. Hali ya foleni\n"
            "2. Huduma zilizopo\n"
            "3. Saa za kazi\n"
            "4. Mawasiliano\n"
            "0. Rudi nyuma"
        ),
        "queue_now": (
            "HALI YA FOLENI - {name}\n"
            "Wagonjwa wanaosubiri: {count}\n"
            "Muda unaokadiriwa: dakika {low}-{high}\n"
            "Taarifa imesasishwa: saa {updated}"
        ),
        "queue_empty": "Hakuna wagonjwa wanaosubiri sasa hivi.\nTaarifa imesasishwa: saa {updated}",
        "services_list": "Huduma zinazopatikana ({name}):\n{services}",
        "services_none": "Hakuna taarifa iliyopatikana.",
        "hours": "Saa za kazi ({name}):\n{opens} - {closes} kila siku",
        "contact_info": "Mawasiliano ({name}):\n{contact}",
        "no_facilities": "Hakuna vituo vya afya vilivyosajiliwa.",
        "guide_menu": (
            "MWONGOZO WA AFYA:\n"
            "1. Dalili za dharura\n"
            "2. Malaria\n"
            "3. Uzazi wa jamii\n"
            "4. UKIMWI (HIV)"
        ),
        "guide_danger": (
            "DALILI ZA DHARURA - fika hospitali SASA:\n"
            "- Kupumua kwa shida\n"
            "- Kudidimia/kuzimia\n"
            "- Mshipuko (mwili kushika)\n"
            "- Damu nyingi bila kushikwa\n"
            "- Maumivu makali ya kifua"
        ),
        "guide_malaria": (
            "MALARIA:\n"
            "- Homa, kihiso, maumivu ya mwili\n"
            "- Lala kwenye neti ya mbu kila usiku\n"
            "- Ukiwa na homa, pima mara moja"
        ),
        "guide_maternal": (
            "UZAZI WA JAMII:\n"
            "- Tembelea kituo cha afya mara 4 wakati wa ujauzito\n"
            "- Fika mara moja ukiwa na dalili za hatari\n"
            "- Jifunze na uliza daktari wako"
        ),
        "guide_hiv": (
            "UKIMWI (HIV):\n"
            "- Vipimo vya bure vya HIV vipo kwenye vituo vya afya\n"
            "- Tumia kondomu kila mara\n"
            "- ART ni bure kwa wenye virusi"
        ),
        "no_appointment": "Hakuna miadi ijayo kwa namba hii. Tumia menyu ya 2 kubook.",
        "appointment_found": (
            "Miadi yako: {day} saa {time}\n"
            "Kituo: {facility}\n"
            "Fika dakika 15 kabla."
        ),
        "slot_header": "Chagua muda wa miadi:",
        "slot_today_tag": "leo",
        "slot_tomorrow_tag": "kesho",
        "no_slots": "Samahani, hakuna nafasi leo na kesho. Jaribu tena kesho asubuhi.",
        "booked_ok": "Miadi imethibitishwa: {label}. Utapokelewa SMS.",
        "queue_status": "Nafasi yako: #{pos}. Wasilisha namba yako ukifika.",
        "queue_none": "Hujaingia kwenye foleni. Tumia menyu ya 1 kuanza.",
        "urgent_queued": "Hali yako ni ya haraka. Umewekwa foleni ya leo, nafasi #{pos}. Fika {facility} sasa.",
        "bye": "Asante kwa kutumia Afya Smart.",
    },
    "en": {
        "welcome": "Welcome to AFYA SMART\n1. Kiswahili\n2. English",
        "menu": (
            "Choose a service:\n"
            "1. Check your symptoms\n"
            "2. Book an appointment\n"
            "3. My queue position\n"
            "4. Find a facility\n"
            "5. Health guide\n"
            "6. My appointments\n"
            "0. Exit"
        ),
        "invalid": "Invalid input. Try again.",
        "region_header": "CHOOSE A REGION:",
        "facility_header": "CHOOSE A FACILITY ({region}):",
        "facility_menu": (
            "{name}\n"
            "1. Queue status\n"
            "2. Available services\n"
            "3. Working hours\n"
            "4. Contact\n"
            "0. Back"
        ),
        "queue_now": (
            "QUEUE STATUS - {name}\n"
            "People waiting: {count}\n"
            "Estimated wait: {low}-{high} minutes\n"
            "Updated: {updated}"
        ),
        "queue_empty": "No one is waiting right now.\nUpdated: {updated}",
        "services_list": "Available services ({name}):\n{services}",
        "services_none": "No information available.",
        "hours": "Working hours ({name}):\n{opens} - {closes} daily",
        "contact_info": "Contact ({name}):\n{contact}",
        "no_facilities": "No registered health facilities.",
        "guide_menu": (
            "HEALTH GUIDE:\n"
            "1. Danger signs\n"
            "2. Malaria\n"
            "3. Maternal health\n"
            "4. HIV/AIDS"
        ),
        "guide_danger": (
            "DANGER SIGNS - go to hospital NOW:\n"
            "- Difficulty breathing\n"
            "- Unconsciousness\n"
            "- Convulsions\n"
            "- Severe bleeding\n"
            "- Severe chest pain"
        ),
        "guide_malaria": (
            "MALARIA:\n"
            "- Fever, chills, body aches\n"
            "- Sleep under a mosquito net every night\n"
            "- If you have fever, get tested immediately"
        ),
        "guide_maternal": (
            "MATERNAL HEALTH:\n"
            "- Attend all 4 antenatal visits\n"
            "- Go to the facility at any danger sign\n"
            "- Ask your doctor questions"
        ),
        "guide_hiv": (
            "HIV/AIDS:\n"
            "- Free HIV testing at health facilities\n"
            "- Always use condoms\n"
            "- ART is free for people living with HIV"
        ),
        "no_appointment": "No upcoming appointment for this number. Use option 2 to book.",
        "appointment_found": (
            "Your appointment: {day} at {time}\n"
            "Facility: {facility}\n"
            "Arrive 15 minutes early."
        ),
        "slot_header": "Choose an appointment time:",
        "slot_today_tag": "today",
        "slot_tomorrow_tag": "tomorrow",
        "no_slots": "Sorry, no slots today or tomorrow. Try again tomorrow morning.",
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


def recommended_slots(db: Session, facility_id: int, limit: int = 3) -> list[Slot]:
    """Slots bora za LEO, na KESHO kama leo imejaa/zimepita.

    Kila slot ina _booking_date ili mtiririko ujue ni siku gani — inazuia
    mgonjwa kubook slot ya leo iliyopita au ku-confuse na ya kesho.
    """
    today = date.today()
    tomorrow = today + timedelta(days=1)

    for day in (today, tomorrow):
        slots = booking_service.available_slots(db, facility_id, day)
        if slots:
            slots.sort(key=forecast.expected_wait_minutes)
            for slot in slots:
                slot._booking_date = day  # noqa: SLF001 — context ya mtiririko
            return slots[:limit]
    return []


def slot_label(slot: Slot, lang: str = "sw") -> str:
    wait = slot.expected_wait_minutes or forecast.expected_wait_minutes(slot)
    day_tag = _t(lang, "slot_tomorrow_tag") if getattr(slot, "_booking_date", None) == date.today() + timedelta(days=1) else _t(lang, "slot_today_tag")
    return f"{day_tag} {slot.start_time.strftime('%H:%M')} (~{wait} min)"


def _render_slot_menu(db: Session, lang: str, facility: Facility) -> str:
    slots = recommended_slots(db, facility.id)
    if not slots:
        return f"END {_t(lang, 'no_slots')}"
    lines = [_t(lang, "slot_header")]
    for idx, slot in enumerate(slots, start=1):
        lines.append(f"{idx}. {slot_label(slot, lang)}")
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

    forecast.update_slot_forecasts(db, facility.id, getattr(slot, "_booking_date", date.today()))
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

    label = slot_label(slot, lang)
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
        return f"END {triage_service.message_for_urgency(urgency, facility.name, queue_pos=pos)}"

    # SELF_CARE
    return f"END {triage_service.message_for_urgency(urgency)}"


# ----------------------------------------------------------------------------
# Menyu mpya: Tafuta hospitali (eneo → kituo → taarifa), Mwongozo wa afya,
# Angalia miadi yangu, na Toka.
# ----------------------------------------------------------------------------
GUIDE_TOPICS = {
    "1": "guide_danger",
    "2": "guide_malaria",
    "3": "guide_maternal",
    "4": "guide_hiv",
}


def _regions_list(db: Session) -> list[str]:
    """Mikoa yote yenye vituo, imepangwa kwa alfabeti."""
    return list(db.scalars(select(Facility.region).distinct().order_by(Facility.region)))


def _facilities_in_region(db: Session, region: str) -> list[Facility]:
    return list(
        db.scalars(select(Facility).where(Facility.region == region).order_by(Facility.name))
    )


def _facility_queue_summary(db: Session, lang: str, facility: Facility) -> str:
    """Hali ya foleni ya kituo: idadi + makadirio ya muda + muda wa kusasisha."""
    count = queue_service.waiting_count(db, facility.id)
    updated = datetime.now().strftime("%H:%M")
    if count == 0:
        return _t(lang, "queue_empty", updated=updated)
    per_patient = queue_service.mean_service_minutes(db, facility.id)
    low = max(5, int(count * per_patient * 0.8))
    high = max(low + 5, int(count * per_patient * 1.3))
    return _t(lang, "queue_now", name=facility.name, count=count, low=low, high=high, updated=updated)


def _handle_facility_search(db: Session, lang: str, elements: list[str]) -> str:
    """Mtiririko wa "Tafuta hospitali": eneo → kituo → taarifa.

    AT hureplay chain nzima kila request — hivyo tunatembeza element za
    mwisho (baada ya "1*4") kupitia state machine ndogo: "0"inarudi nyuma
    hatua moja, jibu batili hubaki kwenye skrini ile ile.
    """
    regions = _regions_list(db)
    if not regions:
        return f"END {_t(lang, 'no_facilities')}"

    stage = "region"
    region: str | None = None
    facility: Facility | None = None

    for el in elements:
        el = el.strip()
        if stage == "region":
            if el == "0":  # Toka
                return f"END {_t(lang, 'bye')}"
            idx = int(el) if el.isdigit() else -1
            if 1 <= idx <= len(regions):
                region = regions[idx - 1]
                stage = "facility"
        elif stage == "facility":
            if el == "0":  # Rudi nyuma → orodha ya mikoa
                region = None
                stage = "region"
                continue
            facilities = _facilities_in_region(db, region)
            idx = int(el) if el.isdigit() else -1
            if 1 <= idx <= len(facilities):
                facility = facilities[idx - 1]
                stage = "info"
        elif stage == "info":
            # Taarifa (1-4) huishisha session kwa END; "0" rudi kwenye orodha.
            if el == "0":
                facility = None
                stage = "facility"
                continue
            if facility is None:
                break
            if el == "1":
                return f"END {_facility_queue_summary(db, lang, facility)}"
            if el == "2":
                services = (facility.services or "").strip() or _t(lang, "services_none")
                return f"END {_t(lang, 'services_list', name=facility.name, services=services)}"
            if el == "3":
                opens = facility.opens_at.strftime("%H:%M") if facility.opens_at else "08:00"
                closes = facility.closes_at.strftime("%H:%M") if facility.closes_at else "17:00"
                return f"END {_t(lang, 'hours', name=facility.name, opens=opens, closes=closes)}"
            if el == "4":
                contact = (facility.contact or "").strip() or _t(lang, "services_none")
                return f"END {_t(lang, 'contact_info', name=facility.name, contact=contact)}"

    # Skrini ya sasa (jibu batili au hatua bado haijajibiwa)
    if stage == "region":
        lines = [_t(lang, "region_header")]
        lines += [f"{i}. {r}" for i, r in enumerate(regions, start=1)]
        lines.append("0. Toka")
        return "CON " + "\n".join(lines)
    if stage == "facility" and region is not None:
        facilities = _facilities_in_region(db, region)
        lines = [_t(lang, "facility_header", region=region)]
        lines += [f"{i}. {f.name}" for i, f in enumerate(facilities, start=1)]
        lines.append("0. Rudi nyuma")
        return "CON " + "\n".join(lines)
    if stage == "info" and facility is not None:
        return "CON " + _t(lang, "facility_menu", name=facility.name)
    return f"CON {_t(lang, 'invalid')}\n" + _t(lang, "menu")


def _handle_health_guide(lang: str, elements: list[str]) -> str:
    """Mwongozo wa afya: orodha ya mada, kila mada inaishisha kwa END."""
    if not elements or elements[-1].strip() not in GUIDE_TOPICS:
        if elements and elements[-1].strip() == "0":
            return f"END {_t(lang, 'bye')}"
        return f"CON {_t(lang, 'guide_menu')}"
    return f"END {_t(lang, GUIDE_TOPICS[elements[-1].strip()])}"


def _handle_my_appointments(db: Session, lang: str, phone_number: str) -> str:
    """Miadi ijayo ya mgonjwa (END — session inaishisha)."""
    today = date.today()
    stmt = (
        select(Appointment, Slot, Facility)
        .join(Slot, Appointment.slot_id == Slot.id)
        .join(Facility, Slot.facility_id == Facility.id)
        .join(Patient, Appointment.patient_id == Patient.id)
        .where(
            Patient.phone_number == phone_number,
            Appointment.status == AppointmentStatus.BOOKED.value,
            Slot.date >= today,
        )
        .order_by(Slot.date, Slot.start_time)
        .limit(1)
    )
    row = db.execute(stmt).first()
    if row is None:
        return f"END {_t(lang, 'no_appointment')}"
    _appointment, slot, facility = row
    if slot.date == today:
        day = _t(lang, "slot_today_tag")
    elif slot.date == today + timedelta(days=1):
        day = _t(lang, "slot_tomorrow_tag")
    else:
        day = slot.date.strftime("%Y-%m-%d")
    return f"END {_t(lang, 'appointment_found', day=day, time=slot.start_time.strftime('%H:%M'), facility=facility.name)}"


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

    choice = levels[1]

    # Chaguo 4/5/6/0 (tafuta hospitali, mwongozo, miadi yangu, toka) hazihitaji
    # kituo chenye nafasi za miadi — zihakikishe kabla ya ukaguzi wa facility.
    if choice == "4":  # Tafuta hospitali (eneo → kituo → taarifa)
        return _handle_facility_search(db, lang, levels[2:])

    if choice == "5":  # Mwongozo wa afya
        return _handle_health_guide(lang, levels[2:])

    if choice == "6":  # Angalia miadi yangu
        return _handle_my_appointments(db, lang, phone_number)

    if choice == "0":  # Toka
        return f"END {_t(lang, 'bye')}"

    facility = get_default_facility(db)
    if facility is None:
        return "END Huduma haipatikani kwa sasa. Jaribu tena baadaye."

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
            slots = recommended_slots(db, facility.id)
            return _book_chosen_slot(
                db, lang, facility, patient, levels[-1], session_row.id, slots
            )
        return _handle_triage_answer(db, lang, levels, session_row, facility)

    if choice == "2":  # booking bila triage
        if len(levels) == 2:
            return _render_slot_menu(db, lang, facility)
        patient = get_or_create_patient(db, phone_number)
        slots = recommended_slots(db, facility.id)
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
