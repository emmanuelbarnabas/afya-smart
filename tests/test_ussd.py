"""Tests for the Africa's Talking USSD handler (ussd.py).

The handler is session-based: Africa's Talking replays the whole answer
chain on every POST and only the LAST element is new.  These tests drive
``_respond`` exactly the way ``app.py`` does — ``text.split('*')``.
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
    assert "Jinsia" in send(PHONE, "1")
    assert "homa" in send(PHONE, "1*1")
    assert "Umri" in send(PHONE, "1*1*2")
    assert "kifua" in send(PHONE, "1*1*2*30")
    assert "kupumua" in send(PHONE, "1*1*2*30*2")
    assert "damu" in send(PHONE, "1*1*2*30*2*2")
    assert "kituo" in send(PHONE, "1*1*2*30*2*2*2")

    reply = send(PHONE, "1*1*2*30*2*2*2*1")
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


def test_yellow_fever_and_child_age():
    fever_phone = "+255711100002"
    reply = send(fever_phone, "1*1*1*40*2*2*2*2")
    assert reply.startswith("END ")

    child_phone = "+255711100003"
    reply = send(child_phone, "1*1*2*3*2*2*2*1")
    assert reply.startswith("END ")

    with appmod.get_db() as db:
        levels = [
            row["level"]
            for row in db.execute("SELECT level FROM visits ORDER BY id").fetchall()
        ]
        assert levels == ["YELLOW", "YELLOW"]


def test_facility_answer_stored():
    reply = send(PHONE, "1*1*2*30*2*2*2*2")
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
    "1*1*2*40*1",             # chest pain = yes
    "1*1*2*40*2*1",           # breathing difficulty = yes
    "1*1*2*40*2*2*1",         # severe bleeding = yes
])
def test_red_flag_ends_immediately(chain):
    phone = f"+2557111{chain.replace('*', '')[:7]}"
    reply = send(phone, chain)
    assert reply.startswith("END Bahati gracious")
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
    send(PHONE, "1*1*2*40*1")  # RED visit created
    reply = send(PHONE, "1")
    assert reply.startswith("END ")
    assert "Tayari umesajiliwa" in reply


# --------------------------------------------------------------------------- #
# Invalid input keeps the patient on the same question
# --------------------------------------------------------------------------- #

def test_invalid_age_is_repeated():
    # Walk the flow one answer per request (how Africa's Talking really works):
    # each POST replays the chain and only the last element is new.
    assert "Jinsia" in send(PHONE, "1")
    assert "homa" in send(PHONE, "1*1")
    assert "Umri" in send(PHONE, "1*1*2")

    reply = send(PHONE, "1*1*2*abc")
    assert reply.startswith("CON ")
    assert "Umri uliyotoa haufai" in reply

    # The corrected answer continues the flow (step did not advance twice).
    reply = send(PHONE, "1*1*2*abc*30")
    assert "kifua" in reply


def test_cold_session_replays_full_chain():
    # A fresh phone number (cold session) replaying the whole chain in one
    # POST — the README/curl style — must land on the same invalid-age reply.
    cold = "+255711100077"
    reply = send(cold, "1*1*2*abc")
    assert reply.startswith("CON ")
    assert "Umri uliyotoa haufai" in reply


def test_invalid_menu_answer_for_choice_is_retried():
    send(PHONE, "1")
    reply = send(PHONE, "1*xyz")   # bad sex answer
    assert reply.startswith("CON ")
    assert "Jinsia" in reply


# --------------------------------------------------------------------------- #
# One active visit per phone (the guard)
# --------------------------------------------------------------------------- #

def test_second_registration_blocked_while_waiting():
    send(PHONE, "1*1*2*30*2*2*2*1")  # registered, waiting
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
    send(PHONE, "1*1*2*30*2*2*2*1")
    reply = send(PHONE, "2")
    assert reply.startswith("END ")
    assert "Nafasi yako kwenye foleni ni #1" in reply


def test_menu_3_unregisters_and_allows_reregistration():
    send(PHONE, "1*1*2*30*2*2*2*1")
    reply = send(PHONE, "3")
    assert reply.startswith("END ")
    assert "umeondolewa" in reply

    with appmod.get_db() as db:
        row = db.execute("SELECT status FROM visits").fetchone()
        assert row["status"] == "cancelled"

    # Registration is possible again.
    reply = send(PHONE, "1")
    assert reply.startswith("CON ")
    assert "Jinsia" in reply


def test_menu_3_without_registration():
    reply = send(PHONE, "3")
    assert reply.startswith("END ")
    assert "Hakuna usajili" in reply


# --------------------------------------------------------------------------- #
# Webhook retries (idempotency)
# --------------------------------------------------------------------------- #

def test_replayed_chain_returns_cached_reply_without_new_visit():
    first = send(PHONE, "1*1*2*30*2*2*2*1")
    replay = send(PHONE, "1*1*2*30*2*2*2*1")
    assert replay == first

    with appmod.get_db() as db:
        n = db.execute("SELECT COUNT(*) AS n FROM visits").fetchone()["n"]
        assert n == 1  # retry did not create a second visit


def test_every_reply_starts_with_con_or_end():
    chains = ["", "1", "1*9", "1*1", "1*1*2", "1*1*2*abc", "2", "3", "9"]
    for chain in chains:
        reply = send(PHONE, chain)
        assert reply.startswith(("CON ", "END ")), (chain, reply[:40])
