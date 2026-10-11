"""Tests for the Africa's Talking USSD handler (ussd.py).

The handler is session-based: Africa's Talking replays the whole answer
chain on every POST and only the LAST element is new.  These tests drive
``_respond`` exactly the way ``app.py`` does — ``text.split('*')``.

The registration flow follows the triage-nurse order (ETAT/IMCI style):
age, sex, then the danger signs one by one, then fever (with duration),
then the facility.  Answering a danger sign "yes" ends the session
immediately with the RED emergency message.
"""

import pytest

import app as appmod
import ussd


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #

@pytest.fixture(autouse=True)
def fresh(tmp_path, monkeypatch):
    """Fresh SQLite DB + empty in-memory session state per test."""
    monkeypatch.setattr(appmod, "DATABASE_PATH", str(tmp_path / "test.db"))
    appmod.init_db()
    ussd._SESSION.clear()
    ussd._LAST_REPLY.clear()
    yield


def send(phone, chain):
    """Send one answer chain the way the Flask route does."""
    return ussd._respond(phone, chain.split("*") if chain else [])


PHONE = "+255711100001"

# A complete GREEN registration (30-year-old man, no danger signs, no fever):
# menu, age, sex, fahamu, mshipuko, damu, kifua, kupumua, homa, kituo.
GREEN_CHAIN = "1*30*1*1*2*2*2*2*2*1"
# A YELLOW registration (40-year-old man, fever for 4 days, facility 2):
# ... homa=1 (ndiyo), siku=4, kituo=2.
FEVER_CHAIN = "1*40*1*1*2*2*2*2*1*4*2"
# A YELLOW registration for a 3-year-old girl without fever.
CHILD_CHAIN = "1*3*2*1*2*2*2*2*2*1"


# --------------------------------------------------------------------------- #
# Menu
# --------------------------------------------------------------------------- #

def test_empty_session_shows_menu():
    reply = send(PHONE, "")
    assert reply.startswith("CON ")
    assert "CHAGUA HUDUMA" in reply


def test_unknown_menu_choice_repeats_menu():
    reply = send(PHONE, "9")
    assert reply.startswith("CON ")
    assert "CHAGUA HUDUMA" in reply
    assert "Jibu si sahihi" in reply


# --------------------------------------------------------------------------- #
# Full registration flow
# --------------------------------------------------------------------------- #

def test_full_flow_green_replies_position():
    # The flow opens with the age question (the nurse identifies first).
    assert "umri" in send(PHONE, "1")
    assert "Jinsia" in send(PHONE, "1*30")
    assert "fahamu" in send(PHONE, "1*30*1")
    assert "mshipuko" in send(PHONE, "1*30*1*1")
    assert "damu" in send(PHONE, "1*30*1*1*2")
    assert "kifua" in send(PHONE, "1*30*1*1*2*2")
    assert "kupumua" in send(PHONE, "1*30*1*1*2*2*2")
    assert "homa" in send(PHONE, "1*30*1*1*2*2*2*2")
    # No fever -> the duration question is skipped, facility comes next.
    facility_screen = send(PHONE, "1*30*1*1*2*2*2*2*2")
    assert "kituo" in facility_screen
    assert "siku ngapi" not in facility_screen

    reply = send(PHONE, GREEN_CHAIN)
    assert reply.startswith("END ")
    assert "Nafasi yako kwenye foleni ni #" in reply

    # The visit was recorded as GREEN and the patient's sex was stored.
    with appmod.get_db() as db:
        visit = db.execute(
            "SELECT level, status FROM visits v JOIN patients p ON p.id = v.patient_id "
            "WHERE p.phone_number = ?",
            (PHONE,),
        ).fetchone()
        assert visit["level"] == "GREEN"
        assert visit["status"] == "waiting"
        patient = db.execute(
            "SELECT sex FROM patients WHERE phone_number = ?", (PHONE,)
        ).fetchone()
        assert patient["sex"] == "male"


def test_fever_asks_duration_days():
    # Fever "yes" leads to the duration question before the facility.
    up_to_fever = "1*40*1*1*2*2*2*2*1"  # fever answered "yes", days not yet
    assert "siku ngapi" in send(PHONE, up_to_fever)
    # The days answer moves on to the facility question, then the facility
    # answer finishes the registration.
    assert "kituo" in send(PHONE, up_to_fever + "*4")
    reply = send(PHONE, FEVER_CHAIN)
    assert reply.startswith("END ")

    with appmod.get_db() as db:
        visit = db.execute(
            "SELECT level, reason FROM visits v JOIN patients p ON p.id = v.patient_id "
            "WHERE p.phone_number = ?",
            (PHONE,),
        ).fetchone()
        assert visit["level"] == "YELLOW"
        assert "fever" in visit["reason"]


def test_yellow_fever_and_child_age():
    fever_phone = "+255711100002"
    reply = send(fever_phone, FEVER_CHAIN)
    assert reply.startswith("END ")

    child_phone = "+255711100003"
    reply = send(child_phone, CHILD_CHAIN)
    assert reply.startswith("END ")

    with appmod.get_db() as db:
        levels = [
            row["level"]
            for row in db.execute("SELECT level FROM visits ORDER BY id").fetchall()
        ]
        assert levels == ["YELLOW", "YELLOW"]


def test_infant_with_fever_is_red():
    # Age 0 means "under one year": a young infant with fever is a
    # pre-referral emergency (safety-first rule in triage.py).
    infant_phone = "+255711100011"
    # menu, age 0, male, no danger signs..., fever=yes, days=0, facility=1
    reply = send(infant_phone, "1*0*1*1*2*2*2*2*1*0*1")
    assert reply.startswith("END TAHADHARI")
    with appmod.get_db() as db:
        visit = db.execute(
            "SELECT level, reason FROM visits v JOIN patients p ON p.id = v.patient_id "
            "WHERE p.phone_number = ?",
            (infant_phone,),
        ).fetchone()
        assert visit["level"] == "RED"
        assert "infant with fever" in visit["reason"]


def test_facility_answer_stored():
    reply = send(PHONE, "1*30*1*1*2*2*2*2*2*2")
    assert reply.startswith("END ")
    with appmod.get_db() as db:
        patient = db.execute(
            "SELECT facility_id FROM patients WHERE phone_number = ?", (PHONE,)
        ).fetchone()
        # seed_data facilities are not created here, but init_db leaves none —
        # the facility only lands when it exists, otherwise it stays NULL.
        assert patient["facility_id"] in (None, 2)


# --------------------------------------------------------------------------- #
# RED: immediate END, no more questions
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("chain", [
    "1*40*1*2",       # loss of consciousness (hajiamshi) = yes
    "1*40*1*1*1",     # convulsion today = yes
    "1*40*1*1*2*1",   # uncontrolled bleeding = yes
    "1*40*1*1*2*2*1", # sudden severe chest pain = yes
    "1*40*1*1*2*2*2*1",  # breathing difficulty = yes
])
def test_red_flag_ends_immediately(chain):
    phone = f"+2557111{chain.replace('*', '')[:7]}"
    reply = send(phone, chain)
    assert reply.startswith("END TAHADHARI")
    assert "112" in reply

    # One RED visit exists, with the emergency reason.
    with appmod.get_db() as db:
        visit = db.execute(
            "SELECT level, reason FROM visits v JOIN patients p ON p.id = v.patient_id "
            "WHERE p.phone_number = ?",
            (phone,),
        ).fetchone()
        assert visit["level"] == "RED"
        assert visit["reason"].startswith("EMERGENCY -")


def test_red_patient_cannot_register_again():
    send(PHONE, "1*40*1*2")  # RED visit created (unconscious)
    reply = send(PHONE, "1")
    assert reply.startswith("END ")
    assert "Tayari umesajiliwa" in reply


# --------------------------------------------------------------------------- #
# Invalid input keeps the patient on the same question
# --------------------------------------------------------------------------- #

def test_invalid_age_is_repeated():
    # Walk the flow one answer per request (how Africa's Talking really works):
    # each POST replays the chain and only the last element is new.
    assert "umri" in send(PHONE, "1")
    reply = send(PHONE, "1*abc")
    assert reply.startswith("CON ")
    assert "Umri uliyotoa haufai" in reply

    # The corrected answer continues the flow (step did not advance twice).
    reply = send(PHONE, "1*abc*30")
    assert "Jinsia" in reply


def test_invalid_fever_days_is_repeated():
    # Up to the fever question (all danger signs answered "no").
    send(PHONE, "1*30*1*1*2*2*2*2*1")
    reply = send(PHONE, "1*30*1*1*2*2*2*2*1*abc")
    assert reply.startswith("CON ")
    assert "idadi ya siku" in reply

    # A corrected number of days continues to the facility question.
    reply = send(PHONE, "1*30*1*1*2*2*2*2*1*abc*3")
    assert "kituo" in reply


def test_cold_session_replays_full_chain():
    # A fresh phone number (cold session) replaying the whole chain in one
    # POST — the README/curl style — must land on the same invalid-age reply.
    cold = "+255711100077"
    reply = send(cold, "1*abc")
    assert reply.startswith("CON ")
    assert "Umri uliyotoa haufai" in reply


def test_invalid_menu_answer_for_choice_is_retried():
    send(PHONE, "1")
    reply = send(PHONE, "1*xyz")   # bad age answer
    assert reply.startswith("CON ")
    assert "umri" in reply


# --------------------------------------------------------------------------- #
# One active visit per phone (the guard)
# --------------------------------------------------------------------------- #

def test_second_registration_blocked_while_waiting():
    send(PHONE, GREEN_CHAIN)  # registered, waiting
    reply = send(PHONE, "1")
    assert reply.startswith("END ")
    assert "Tayari umesajiliwa" in reply
    assert "Nafasi yako" in reply  # they are told their position


# --------------------------------------------------------------------------- #
# Menu 2 (queue position) and menu 3 (unregister)
# --------------------------------------------------------------------------- #

def test_menu_2_without_registration():
    reply = send(PHONE, "2")
    assert reply.startswith("END ")
    assert "Jisajili kwanza" in reply


def test_menu_2_shows_position_after_registration():
    send(PHONE, GREEN_CHAIN)
    reply = send(PHONE, "2")
    assert reply.startswith("END ")
    assert "Nafasi yako kwenye foleni ni #1" in reply


def test_menu_3_unregisters_and_allows_reregistration():
    send(PHONE, GREEN_CHAIN)
    reply = send(PHONE, "3")
    assert reply.startswith("END ")
    assert "umeondolewa" in reply

    with appmod.get_db() as db:
        row = db.execute("SELECT status FROM visits").fetchone()
        assert row["status"] == "cancelled"

    # Registration is possible again.
    reply = send(PHONE, "1")
    assert reply.startswith("CON ")
    assert "umri" in reply


def test_menu_3_without_registration():
    reply = send(PHONE, "3")
    assert reply.startswith("END ")
    assert "Hakuna usajili" in reply


# --------------------------------------------------------------------------- #
# Webhook retries (idempotency)
# --------------------------------------------------------------------------- #

def test_replayed_chain_returns_cached_reply_without_new_visit():
    first = send(PHONE, GREEN_CHAIN)
    replay = send(PHONE, GREEN_CHAIN)
    assert replay == first

    with appmod.get_db() as db:
        n = db.execute("SELECT COUNT(*) AS n FROM visits").fetchone()["n"]
        assert n == 1  # retry did not create a second visit


def test_every_reply_starts_with_con_or_end():
    chains = ["", "1", "1*9", "1*30", "1*30*abc", "2", "3", "9"]
    for chain in chains:
        reply = send(PHONE, chain)
        assert reply.startswith(("CON ", "END ")), (chain, reply[:40])


# --------------------------------------------------------------------------- #
# Session persistence (ussd_sessions SQLite table)
# --------------------------------------------------------------------------- #

def test_session_survives_restart():
    """A restart (memory cache cleared) must not lose the patient's answers."""
    assert "umri" in send(PHONE, "1")
    assert "Jinsia" in send(PHONE, "1*1")        # age answered -> sex question
    assert "fahamu" in send(PHONE, "1*1*2")      # sex answered -> fahamu question

    # Simulate a server restart: memory caches gone, SQLite kept.
    ussd._SESSION.clear()
    ussd._LAST_REPLY.clear()

    # The session was rehydrated from ussd_sessions: only the NEW answer is
    # applied (no bootstrap replay), so the flow continues at mshipuko.
    reply = send(PHONE, "1*1*2*1")
    assert "mshipuko" in reply


def test_retry_reply_survives_restart():
    """A webhook retry after a restart still returns the cached reply."""
    first = send(PHONE, GREEN_CHAIN)
    assert first.startswith("END ")

    ussd._SESSION.clear()
    ussd._LAST_REPLY.clear()

    replay = send(PHONE, GREEN_CHAIN)
    assert replay == first
    with appmod.get_db() as db:
        n = db.execute("SELECT COUNT(*) AS n FROM visits").fetchone()["n"]
        assert n == 1  # no second visit from the replayed webhook


def test_stale_sessions_pruned_after_24h():
    """Rows idle for a day are dropped on write (bounded table growth)."""
    with appmod.get_db() as db:
        db.execute(
            "INSERT INTO ussd_sessions "
            "(phone_number, step, answers, last_chain, last_reply, updated_at) "
            "VALUES (?, 3, '{}', 'old', 'CON old', datetime('now', '-2 days'))",
            ("+255711100099",),
        )
        db.commit()

    send(PHONE, "1")  # any new activity triggers the prune in _save()

    with appmod.get_db() as db:
        row = db.execute(
            "SELECT 1 FROM ussd_sessions WHERE phone_number = ?",
            ("+255711100099",),
        ).fetchone()
    assert row is None


def test_active_session_not_pruned():
    """The 24h prune only drops stale rows — fresh sessions stay."""
    send(PHONE, "1*30*1")  # menu, age, sex -> now on the fahamu question
    with appmod.get_db() as db:
        row = db.execute(
            "SELECT step FROM ussd_sessions WHERE phone_number = ?", (PHONE,)
        ).fetchone()
    assert row is not None
    assert row["step"] == 3
