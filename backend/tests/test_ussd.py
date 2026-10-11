"""Tests za USSD flow — language, triage (kila urgency), booking, foleni.

Kumbuka: AT inatuma path nzima kila wakati; kila request inaongeza jibu MOJA.
Hivyo test zinatembea hatua kwa hatua kama simu halisi ingefanya.
"""
from app.models.scheduling import Appointment, QueueEntry, QueueStatus
from app.models.triage import TriageSession


def _post(client, text: str, session_id: str = "ATSession1", phone: str = "+255700111222"):
    return client.post(
        "/api/v1/ussd",
        data={"sessionId": session_id, "phoneNumber": phone, "text": text, "serviceCode": "*384*123#"},
    )


def _walk_triage(client, answers: list[str], session_id: str, phone: str = "+255700111222"):
    """Tembea mtiririko mzima wa triage hatua kwa hatua; return jibu la mwisho."""
    responses = [_post(client, "1*1", session_id, phone)]
    for i in range(len(answers)):
        text = "1*1*" + "*".join(answers[: i + 1])
        responses.append(_post(client, text, session_id, phone))
    return responses[-1]


def test_welcome_screen(client):
    resp = _post(client, "")
    assert resp.status_code == 200
    assert resp.text.startswith("CON ")
    assert "AFYA SMART" in resp.text


def test_response_is_plain_text_not_json(client):
    resp = _post(client, "")
    assert resp.headers["content-type"].startswith("text/plain")


def test_language_selection_swahili(client):
    resp = _post(client, "1")
    assert resp.status_code == 200
    assert resp.text.startswith("CON ")
    assert "Chagua huduma" in resp.text


def test_language_selection_english(client):
    resp = _post(client, "2")
    assert "Choose a service" in resp.text


def test_triage_emergency_flow(client, facility, patient):
    # breathing=1, conscious=0 → dalili 2 za dharura
    resp = _walk_triage(client, ["1", "0", "0", "0", "0", "0"], session_id="sess-emg")
    assert resp.text.startswith("END ")
    assert "DHARURA" in resp.text


def test_triage_urgent_joins_queue(client, facility, patient, slots_today, db_session):
    # bleeding=1 pekee, hakuna risk group → URGENT
    resp = _walk_triage(client, ["0", "1", "1", "0", "0", "0"], session_id="sess-urgent")
    assert resp.text.startswith("END ")
    assert "haraka" in resp.text
    entry = db_session.query(QueueEntry).first()
    assert entry is not None
    assert entry.status == QueueStatus.WAITING.value


def test_triage_routine_shows_slot_menu_then_books(client, facility, patient, slots_today, db_session):
    # fever=1, pain=1 → ROUTINE
    resp = _walk_triage(client, ["0", "1", "0", "1", "1", "0"], session_id="sess-routine")
    assert resp.text.startswith("CON ")
    assert "Chagua muda" in resp.text

    # Chagua slot ya kwanza
    resp = _post(client, "1*1*0*1*0*1*1*0*1", session_id="sess-routine")
    assert resp.text.startswith("END ")
    assert "imethibitishwa" in resp.text

    appointment = db_session.query(Appointment).first()
    assert appointment is not None
    assert appointment.triage_session_id is not None
    session_row = db_session.query(TriageSession).filter(TriageSession.id == appointment.triage_session_id).first()
    assert session_row.urgency == "routine"
    assert session_row.outcome == "slot_booked"


def test_triage_self_care(client, facility, patient, slots_today):
    # Hakuna dalili kubwa → SELF_CARE
    resp = _walk_triage(client, ["0", "1", "0", "0", "0", "0"], session_id="sess-healthy")
    assert resp.text.startswith("END ")
    assert "nyumbani" in resp.text


def test_triage_invalid_input_reprompts(client, facility, patient):
    resp = _post(client, "1*1", session_id="sess-invalid")  # anza session
    assert resp.text.startswith("CON ")
    resp = _post(client, "1*1*9", session_id="sess-invalid")  # jibu batili
    assert resp.text.startswith("CON ")
    assert "Jibu si sahihi" in resp.text
    # Jibu sahihi baada ya kosa linaendelea vizuri
    resp = _post(client, "1*1*9*0", session_id="sess-invalid")
    assert resp.text.startswith("CON ")  # swali la pili


def test_booking_menu_without_triage(client, facility, patient, slots_today):
    resp = _post(client, "1*2", session_id="sess-book")
    assert resp.text.startswith("CON ")
    assert "Chagua muda" in resp.text


def test_booking_slot_via_menu(client, facility, patient, slots_today, db_session):
    resp = _post(client, "1*2*1", session_id="sess-book")
    assert resp.text.startswith("END ")
    assert "imethibitishwa" in resp.text
    appointment = db_session.query(Appointment).first()
    assert appointment is not None
    assert appointment.status == "booked"
    slot = appointment.slot
    assert slot.booked == 1


def test_queue_position(client, facility, patient, slots_today, db_session):
    entry = QueueEntry(facility_id=facility.id, patient_id=patient.id, status=QueueStatus.WAITING.value)
    db_session.add(entry)
    db_session.commit()

    resp = _post(client, "1*3", session_id="sess-pos")
    assert resp.text.startswith("END ")
    assert "#1" in resp.text


def test_queue_position_empty(client, facility, patient):
    resp = _post(client, "1*3", session_id="sess-nopos")
    assert resp.text.startswith("END ")
    assert "Hujaingia" in resp.text


def test_full_session_persisted_in_db(client, facility, patient, slots_today, db_session):
    _walk_triage(client, ["0", "1", "0", "0", "0", "0"], session_id="sess-db")
    session_row = db_session.query(TriageSession).filter(TriageSession.at_session_id == "sess-db").first()
    assert session_row is not None
    assert session_row.urgency == "self_care"
    assert len(session_row.answers) == 6
    # ML model halisi (ml-v2) — rules-v2 ni fallback tu
    assert session_row.model_version in ("ml-v2", "ml-v2+safety", "rules-v2")


# --------------------------------------------------------------------------- #
# Menyu mpya: Tafuta hospitali, Mwongozo wa afya, Miadi yangu, Toka
# --------------------------------------------------------------------------- #
def test_menu_shows_new_options(client):
    resp = _post(client, "1")
    assert "Tafuta hospitali" in resp.text
    assert "Mwongozo wa afya" in resp.text
    assert "Angalia miadi yangu" in resp.text
    assert "0. Toka" in resp.text


def test_exit_option(client):
    resp = _post(client, "1*0", session_id="sess-exit")
    assert resp.text.startswith("END ")
    assert "Asante" in resp.text


def test_facility_search_region_menu(client, facility):
    resp = _post(client, "1*4", session_id="sess-fac")
    assert resp.text.startswith("CON ")
    assert "CHAGUA ENEO" in resp.text
    assert "Dar es Salaam" in resp.text


def test_facility_search_facility_list(client, facility):
    resp = _post(client, "1*4*1", session_id="sess-fac")
    assert resp.text.startswith("CON ")
    assert "CHAGUA HOSPITALI" in resp.text
    assert "Test Dispensary" in resp.text


def test_facility_info_menu(client, facility):
    resp = _post(client, "1*4*1*1", session_id="sess-fac")
    assert resp.text.startswith("CON ")
    assert "Hali ya foleni" in resp.text
    assert "Huduma zilizopo" in resp.text
    assert "Saa za kazi" in resp.text
    assert "Mawasiliano" in resp.text


def test_facility_queue_status(client, facility):
    resp = _post(client, "1*4*1*1*1", session_id="sess-fac")
    assert resp.text.startswith("END ")
    assert "wanaosubiri" in resp.text
    assert "imesasishwa" in resp.text


def test_facility_services(client, facility, db_session):
    from app.models.facility import Facility

    f = db_session.query(Facility).first()
    f.services = "Malaria,Watoto"
    db_session.commit()

    resp = _post(client, "1*4*1*1*2", session_id="sess-fac")
    assert resp.text.startswith("END ")
    assert "Malaria" in resp.text
    assert "Watoto" in resp.text


def test_facility_hours(client, facility):
    resp = _post(client, "1*4*1*1*3", session_id="sess-fac")
    assert resp.text.startswith("END ")
    assert "Saa za kazi" in resp.text
    assert "08:00" in resp.text


def test_facility_contact(client, facility, db_session):
    from app.models.facility import Facility

    f = db_session.query(Facility).first()
    f.contact = "+255 712 345 678"
    db_session.commit()

    resp = _post(client, "1*4*1*1*4", session_id="sess-fac")
    assert resp.text.startswith("END ")
    assert "+255 712 345 678" in resp.text


def test_facility_search_back_navigation(client, facility):
    # Rudi nyuma kutoka orodha ya vituo → orodha ya mikoa
    resp = _post(client, "1*4*1*0", session_id="sess-fac")
    assert resp.text.startswith("CON ")
    assert "CHAGUA ENEO" in resp.text


def test_health_guide_menu(client):
    resp = _post(client, "1*5", session_id="sess-guide")
    assert resp.text.startswith("CON ")
    assert "MWONGOZO WA AFYA" in resp.text
    assert "Dalili za dharura" in resp.text


def test_health_guide_topic(client):
    resp = _post(client, "1*5*1", session_id="sess-guide")
    assert resp.text.startswith("END ")
    assert "DHARURA" in resp.text
    assert "Kupumua kwa shida" in resp.text


def test_health_guide_malaria_topic(client):
    resp = _post(client, "1*5*2", session_id="sess-guide")
    assert resp.text.startswith("END ")
    assert "MALARIA" in resp.text


def test_my_appointments_none(client, facility, patient):
    resp = _post(client, "1*6", session_id="sess-appt")
    assert resp.text.startswith("END ")
    assert "Hakuna miadi" in resp.text


def test_my_appointments_found(client, facility, patient, slots_today, db_session):
    from app.models.scheduling import Appointment

    db_session.add(Appointment(patient_id=patient.id, slot_id=slots_today[0].id))
    db_session.commit()

    resp = _post(client, "1*6", session_id="sess-appt")
    assert resp.text.startswith("END ")
    assert "Miadi yako" in resp.text
    assert "Test Dispensary" in resp.text


def test_facilities_api_includes_services_and_contact(client, facility, db_session):
    from app.models.facility import Facility

    f = db_session.query(Facility).first()
    f.services = "Malaria"
    f.contact = "+255 712 345 678"
    db_session.commit()

    resp = client.get("/api/v1/facilities")
    assert resp.status_code == 200
    item = resp.json()[0]
    assert item["services"] == "Malaria"
    assert item["contact"] == "+255 712 345 678"
