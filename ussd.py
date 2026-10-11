"""Afya Smart — USSD entry point (the patient-facing channel).

This is the only file a patient (or a nurse testing the flow from a phone)
will ever touch.  It follows the Africa's Talking USSD protocol:

    * Africa's Talking POSTs form fields (phoneNumber, text, sessionId, ...).
    * ``text`` is the chain of everything typed so far, joined with ``*``:
        - first request:  ""       -> show the menu
        - then:           "1"      -> menu choice (registration)
        - later:          "1*30"    -> age answered, sex question shown
        - a bad answer:   "1*30*abc" -> stays on the same question
    * Every reply must start with "CON " (keep the session open) or "END "
      (close the session).

The handler is **session-based**: Africa's Talking replays the whole chain on
every request, but only the LAST element is the patient's newest answer, so
the step lives in a per-phone session (``_SESSION``).  A rejected answer is
never lost: it stays in the chain, the step does not advance, and the patient
is asked the same question again.

Webhook retries are handled by remembering the last chain + reply per phone:
a replayed POST returns the cached reply and never inserts a second visit.
Sessions persist in the ``ussd_sessions`` SQLite table, so a server restart
never loses a half-finished registration; rows idle for 24h are pruned.

There is exactly one active visit per phone number: if a patient has already
registered (their visit is still waiting / called / in consult) they are told
their queue position instead of registering again.
"""

from __future__ import annotations

import json

from app import get_db
from triage import triage

# --------------------------------------------------------------------------- #
# Session state (write-through cache over the ussd_sessions SQLite table)
# --------------------------------------------------------------------------- #
# One active registration per phone number.  The dicts below are only a
# cache; the source of truth is the ``ussd_sessions`` table (created in
# app.init_db), so a server restart rehydrates the step instead of losing
# the patient's answers.
# phone_number -> {"step": int, "answers": {key: value}}
#   step 0        = menu shown, waiting for the menu choice
#   step 1..N     = answering STEPS[step - 1]
#   step N + 1    = registration finished (session closed by the END reply)
_SESSION: dict = {}

# Idempotency cache for Africa's Talking webhook retries:
# phone_number -> (chain_text, reply).  A replayed chain gets the same reply.
_LAST_REPLY: dict = {}

_SESSION_TTL_CHAINS = 500  # soft cap: drop everything if the store grows too big


def _reset_session(phone_number):
    """Start a fresh registration session for this phone number."""
    if len(_SESSION) > _SESSION_TTL_CHAINS:
        _SESSION.clear()
    _SESSION[phone_number] = {"step": 0, "answers": {}}


def _get_session(phone_number):
    """Return the session for this phone number (created if missing)."""
    s = _SESSION.get(phone_number)
    if s is None:
        _reset_session(phone_number)
        s = _SESSION[phone_number]
    return s


def _clear_session(phone_number):
    """Forget the active registration (an END reply closes it).

    Memory only: the next ``_save()`` writes the cleared state back to
    SQLite, so the retry cache for the last chain still survives.
    """
    _SESSION.pop(phone_number, None)


def _forget(phone_number):
    """Drop everything we know about this phone (fresh session start)."""
    _SESSION.pop(phone_number, None)
    _LAST_REPLY.pop(phone_number, None)
    with get_db() as db:
        db.execute(
            "DELETE FROM ussd_sessions WHERE phone_number = ?", (phone_number,)
        )
        db.commit()


def _hydrate(db, phone_number):
    """Pull this phone's session + last reply back from SQLite.

    Called on every request; a no-op while the memory cache is warm.  This
    is what makes a server restart harmless in the middle of a registration.
    """
    if phone_number in _SESSION and phone_number in _LAST_REPLY:
        return
    row = db.execute(
        "SELECT step, answers, last_chain, last_reply FROM ussd_sessions "
        "WHERE phone_number = ?",
        (phone_number,),
    ).fetchone()
    if row is None:
        return
    if phone_number not in _SESSION and row["step"] is not None:
        _SESSION[phone_number] = {
            "step": row["step"],
            "answers": json.loads(row["answers"] or "{}"),
        }
    if phone_number not in _LAST_REPLY and row["last_chain"] is not None:
        _LAST_REPLY[phone_number] = (row["last_chain"], row["last_reply"])


def _save(db, phone_number, chain, reply):
    """Persist this phone's session + last reply, then prune stale rows.

    The session may have been closed while processing (END reply): step and
    answers are then stored as NULL while the retry cache still survives.
    Rows idle for more than 24 hours are dropped so the table stays bounded
    (growth is no longer unbounded memory only).
    """
    session = _SESSION.get(phone_number)
    db.execute(
        """
        INSERT INTO ussd_sessions
            (phone_number, step, answers, last_chain, last_reply, updated_at)
        VALUES (?, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT(phone_number) DO UPDATE SET
            step = excluded.step,
            answers = excluded.answers,
            last_chain = excluded.last_chain,
            last_reply = excluded.last_reply,
            updated_at = excluded.updated_at
        """,
        (
            phone_number,
            session["step"] if session else None,
            json.dumps(session["answers"], ensure_ascii=False) if session else None,
            chain,
            reply,
        ),
    )
    db.execute(
        "DELETE FROM ussd_sessions "
        "WHERE updated_at < strftime('%Y-%m-%d %H:%M:%S', 'now', '-1 day')"
    )
    db.commit()


# --------------------------------------------------------------------------- #
# USSD strings (Kiswahili)
# --------------------------------------------------------------------------- #
# The wording below follows the way a triage nurse actually opens a
# consultation in a Tanzanian health centre (ETAT / IMCI order): identify the
# patient, then screen the danger signs one by one, then take the history.
# Every reply must start with "CON " (continue) or "END " (close session).
MENU = (
    "CON CHAGUA HUDUMA:\n"
    "1. Kusajiliwa na kuangalia dalili zako (triage)\n"
    "2. Kuona nafasi yako kwenye foleni\n"
    "3. Ondoa usajili wako\n"
)

QUESTION_AGE = (
    "Andika umri wa mgonjwa kwa miaka (mfano 30).\n"
    "Mtoto ambaye hajafika mwaka 1: andika 0.\n"
)
QUESTION_SEX = "Jinsia: 1=Mwanaume 2=Mwanamke\n"
QUESTION_CONSCIOUS = (
    "Je, mgonjwa yuko fahamu (anatambua na anazungumza)?\n"
    "1=Ndiyo 2=Hapana (kudidimia/kuzimia)\n"
)
QUESTION_CONVULSION = (
    "Je, ameshika mshipuko leo (mwili kushika/kupindapinda)?\n"
    "1=Ndiyo 2=Hapana\n"
)
QUESTION_BLEED = (
    "Je, kuna sehemu inayotokwa damu nyingi bila kushikwa?\n"
    "1=Ndiyo 2=Hapana\n"
)
QUESTION_CHEST = (
    "Je, kuna maumivu makali ya kifua yanayoanza ghafla?\n"
    "1=Ndiyo 2=Hapana\n"
)
QUESTION_BREATH = (
    "Je, ana shida ya kupumua (anapumua kwa shida au kwa haraka)?\n"
    "1=Ndiyo 2=Hapana\n"
)
QUESTION_FEVER = "Je, ana homa (mwili wa joto)? 1=Ndiyo 2=Hapana\n"
QUESTION_FEVER_DAYS = (
    "Homa imekuwepo kwa siku ngapi? Andika idadi (mfano 3).\n"
)
QUESTION_FACILITY = "Ni kituo gani unachotembelea? 1=Msasani 2=Kapoleni 3=Nyingine\n"

# RED (emergency) reply — tells the patient to go to the hospital NOW.  No
# queue slot is given because the patient must not wait in line.
RED_MESSAGE = (
    "END TAHADHARI - hii ni dharura ya kiafya.\n"
    "Mgonjwa afike kituo cha afya au wodi ya dharura SASA HIVI.\n"
    "Kama hauna usafiri, piga 112 (dharura ya taifa).\n"
)

ERROR_MESSAGE = "Jibu si sahihi. Andika tena.\n"
INVALID_AGE_MESSAGE = (
    "Umri uliyotoa haufai. Andika umri kwa miaka (mfano 30).\n"
    "Mtoto ambaye hajafika mwaka 1: andika 0.\n"
)
INVALID_DAYS_MESSAGE = "Jibu si sahihi. Andika idadi ya siku (mfano 3).\n"

SUCCES_NAFASI_MESSAGE = "Nafasi yako kwenye foleni ni #{position}."

# --------------------------------------------------------------------------- #
# Question definitions
# --------------------------------------------------------------------------- #
# The registration flow after the menu choice "1".  ``parse`` maps the raw
# answer string to a typed value, or returns None when the answer is invalid
# (the patient stays on the same screen and is asked again).
#
# Order matters clinically: identity (age, sex) then the ETAT/IMCI danger
# signs — a patient who reports a danger sign is told to go to the hospital
# immediately and never has to answer the remaining questions.  The fever
# duration is asked only when the patient actually has fever (``when``).
STEPS = [
    {
        "key": "age",
        "prompt": QUESTION_AGE,
        "parse": lambda raw: (
            int(raw) if raw.isdigit() and 0 <= int(raw) <= 130 else None
        ),
        "invalid_message": INVALID_AGE_MESSAGE,
    },
    {
        "key": "sex",
        "prompt": QUESTION_SEX,
        "parse": lambda raw: {"1": "male", "2": "female"}.get(raw),
    },
    {
        "key": "loss_of_consciousness",
        "prompt": QUESTION_CONSCIOUS,
        # "2 = Hapana" answers the danger question "hajiamshi" -> True.
        "parse": lambda raw: {"1": False, "2": True}.get(raw),
    },
    {
        "key": "convulsion",
        "prompt": QUESTION_CONVULSION,
        "parse": lambda raw: {"1": True, "2": False}.get(raw),
    },
    {
        "key": "severe_bleeding",
        "prompt": QUESTION_BLEED,
        "parse": lambda raw: {"1": True, "2": False}.get(raw),
    },
    {
        "key": "chest_pain",
        "prompt": QUESTION_CHEST,
        "parse": lambda raw: {"1": True, "2": False}.get(raw),
    },
    {
        "key": "breathing_difficulty",
        "prompt": QUESTION_BREATH,
        "parse": lambda raw: {"1": True, "2": False}.get(raw),
    },
    {
        "key": "fever",
        "prompt": QUESTION_FEVER,
        "parse": lambda raw: {"1": True, "2": False}.get(raw),
    },
    {
        "key": "fever_days",
        "prompt": QUESTION_FEVER_DAYS,
        # Only asked when the fever answer was "yes" (see ``when`` below).
        "parse": lambda raw: (
            int(raw) if raw.isdigit() and 0 <= int(raw) <= 365 else None
        ),
        "invalid_message": INVALID_DAYS_MESSAGE,
        "when": lambda answers: answers.get("fever") is True,
    },
    {
        "key": "facility",
        "prompt": QUESTION_FACILITY,
        "parse": lambda raw: {"1": 1, "2": 2, "3": 3}.get(raw),
    },
]

# Red flags: an immediate "yes" ends the session with the RED emergency
# message (the patient is sent straight to the hospital — no more questions).
# These are the ETAT/IMCI danger signs plus the two adult emergency screens.
RED_FLAG_KEYS = {
    "loss_of_consciousness",
    "convulsion",
    "severe_bleeding",
    "chest_pain",
    "breathing_difficulty",
}

# --------------------------------------------------------------------------- #
# Small "database" helpers (Flask + SQLite)
# --------------------------------------------------------------------------- #


def _get_patient(db, phone_number):
    """Return the patient with this phone number (None if not found)."""
    cur = db.execute("SELECT * FROM patients WHERE phone_number = ?", (phone_number,))
    return cur.fetchone()


def _patient_id(db, phone_number):
    """Get or create a patient record for this phone number."""
    row = _get_patient(db, phone_number)
    if row is not None:
        return row["id"]
    cur = db.execute(
        "INSERT INTO patients (phone_number, full_name) VALUES (?, ?)",
        (phone_number, "Mgonjwa (USSD)"),
    )
    db.commit()
    return cur.lastrowid


def _latest_active_visit(db, phone_number):
    """Latest visit that is not finished/cancelled (None if none)."""
    cur = db.execute(
        """
        SELECT v.id, v.status, v.joined_at
        FROM visits v
        JOIN patients p ON p.id = v.patient_id
        WHERE p.phone_number = ?
          AND v.status NOT IN ('finished', 'cancelled')
        ORDER BY v.joined_at DESC, v.id DESC
        LIMIT 1
        """,
        (phone_number,),
    )
    return cur.fetchone()


def _patient_has_active_visit(db, phone_number):
    """A patient has an active visit when their latest visit is not finished."""
    return _latest_active_visit(db, phone_number) is not None


def _queue_position(db, visit_id, joined_at):
    """1-based position of a waiting visit among all waiting visits."""
    cur = db.execute(
        """
        SELECT COUNT(*) AS n
        FROM visits
        WHERE status = 'waiting'
          AND (joined_at < ? OR (joined_at = ? AND id <= ?))
        """,
        (joined_at, joined_at, visit_id),
    )
    row = cur.fetchone()
    return int(row["n"]) if row else 1


def _create_visit(db, patient_id, level, reason):
    """Record a new visit. Returns the row id."""
    cur = db.execute(
        "INSERT INTO visits (patient_id, level, reason) VALUES (?, ?, ?)",
        (patient_id, level, reason),
    )
    db.commit()
    return cur.lastrowid


def _log_audit(db, actor, action, table_name, record_id, detail=""):
    """Append one line to the audit trail. Always succeed, never crash."""
    try:
        db.execute(
            """
            INSERT INTO audit_log (actor, action, table_name, record_id, detail)
            VALUES (?, ?, ?, ?, ?)
            """,
            (actor, action, table_name, record_id, detail),
        )
        db.commit()
    except Exception:
        # The audit log must never take down a live USSD session.
        db.rollback()


def _resolve_facility(db, choice):
    """Map a facility choice ("1"/"2"/"3") to a seeded facility id (or None)."""
    if choice in ("1", "2", "3"):
        cur = db.execute(
            "SELECT id FROM facilities ORDER BY id LIMIT 1 OFFSET ?",
            (int(choice) - 1,),
        )
        row = cur.fetchone()
        if row is not None:
            return row["id"]
    return None


def _get_form_value(form, key, default=""):
    """Read one Africa's Talking form field, returning a string."""
    value = form.get(key, default)
    return value if isinstance(value, str) else str(value)


# --------------------------------------------------------------------------- #
# Menu actions (choices 2 and 3 — these close the session with END)
# --------------------------------------------------------------------------- #


def _menu_show_position(db, phone_number):
    """Menu 2: show the caller's queue position (END — session closes)."""
    visit = _latest_active_visit(db, phone_number)
    if visit is None:
        return "END Hakuna nafasi iliyopimwa kwa namba hii. Jisajili kwanza (1).\n"
    if visit["status"] != "waiting":
        return (
            f"END Umeshwa kwenye foleni (hali: {visit['status']}).\n"
            "Asante kwa kutumia Afya Smart.\n"
        )
    position = _queue_position(db, visit["id"], visit["joined_at"])
    return f"END {SUCCES_NAFASI_MESSAGE.format(position=position)}\n"


def _menu_unregister(db, phone_number):
    """Menu 3: cancel the caller's active visit (END — session closes)."""
    visit = _latest_active_visit(db, phone_number)
    if visit is None:
        return "END Hakuna usajili uliopo kwa namba hii.\n"
    db.execute("UPDATE visits SET status = 'cancelled' WHERE id = ?", (visit["id"],))
    db.commit()
    _log_audit(db, "ussd", "unregister", "visits", visit["id"], "cancelled via USSD menu")
    return "END Usajili wako kwenye foleni umeondolewa.\n"


def _active_visit_reply(db, phone_number):
    """Reply shown when a patient who is already registered picks menu 1."""
    visit = _latest_active_visit(db, phone_number)
    if visit is None:
        return None
    if visit["status"] == "waiting":
        position = _queue_position(db, visit["id"], visit["joined_at"])
        return (
            "END Tayari umesajiliwa kwenye foleni.\n"
            f"{SUCCES_NAFASI_MESSAGE.format(position=position)}\n"
        )
    return f"END Tayari umesajiliwa (hali: {visit['status']}).\n"


# --------------------------------------------------------------------------- #
# Registration flow
# --------------------------------------------------------------------------- #


def _finish_registration(db, phone_number, answers):
    """Run triage, record the visit, reply END.

    ``answers`` may be incomplete when the patient aborts early with a RED
    flag (chest pain / breathing difficulty / severe bleeding) — unanswered
    questions default to "no".
    """
    # One more guard: never create a second active visit for the same phone
    # (covers a retry that raced past the menu check).
    already = _active_visit_reply(db, phone_number)
    if already is not None:
        return already

    symptoms = {
        "loss_of_consciousness": answers.get("loss_of_consciousness", False),
        "convulsion": answers.get("convulsion", False),
        "chest_pain": answers.get("chest_pain", False),
        "breathing_difficulty": answers.get("breathing_difficulty", False),
        "severe_bleeding": answers.get("severe_bleeding", False),
        "fever": answers.get("fever", False),
        "fever_days": answers.get("fever_days"),
        "age": answers.get("age"),
    }
    level, reason = triage(symptoms)

    pid = _patient_id(db, phone_number)

    # Remember what the answers told us (sex, chosen facility) on the patient
    # row — the facility only lands if it actually exists in ``facilities``.
    updates, params = [], []
    if "sex" in answers:
        updates.append("sex = ?")
        params.append(answers["sex"])
    if "facility" in answers:
        facility = _resolve_facility(db, str(answers["facility"]))
        if facility is not None:
            updates.append("facility_id = ?")
            params.append(facility)
    if updates:
        params.append(pid)
        db.execute(f"UPDATE patients SET {', '.join(updates)} WHERE id = ?", params)
        db.commit()

    visit_id = _create_visit(db, pid, level, reason)
    _log_audit(db, "ussd", "register", "visits", visit_id, reason)

    if level == "RED":
        # RED patients go straight to the hospital.  No queue number.
        return RED_MESSAGE

    # Non-RED patients get their real position in the waiting queue.
    cur = db.execute("SELECT joined_at FROM visits WHERE id = ?", (visit_id,))
    joined_at = cur.fetchone()["joined_at"]
    position = _queue_position(db, visit_id, joined_at)
    return (
        f"END {SUCCES_NAFASI_MESSAGE.format(position=position)}\n"
        "Asante kwa kutumia Afya Smart!\n"
    )


def _step_applies(step, answers):
    """True when this question should be asked for the answers so far.

    A step may declare ``when`` — a predicate over the answers collected
    so far (e.g. the fever-duration question is only asked when the patient
    actually has fever).  Skipped steps are stepped over without consuming
    an answer from the chain, identically on a live flow and on a cold-start
    replay, so the chain always lines up.
    """
    when = step.get("when")
    return when is None or when(answers)


def _advance_registration(db, phone_number, session, newest_answer):
    """Apply the patient's newest answer to the current question.

    Returns the USSD reply ("CON ..." to continue, "END ..." when done).
    """
    step_index = session["step"] - 1  # step 1 == STEPS[0]
    step = STEPS[step_index]

    parsed = step["parse"](newest_answer.strip())
    if parsed is None:
        # Invalid: stay on the same question (step does not advance).
        invalid = step.get("invalid_message", ERROR_MESSAGE)
        return f"CON {invalid}{step['prompt']}"

    session["answers"][step["key"]] = parsed
    session["step"] += 1

    # Skip questions that do not apply (e.g. fever duration when there is
    # no fever) before deciding what to ask next.
    while session["step"] <= len(STEPS) and not _step_applies(
        STEPS[session["step"] - 1], session["answers"]
    ):
        session["step"] += 1

    # Red flag answered YES → immediate END (README: no queue slot, do not
    # make an emergency patient answer more questions).
    if step["key"] in RED_FLAG_KEYS and parsed is True:
        _clear_session(phone_number)
        return _finish_registration(db, phone_number, session["answers"])

    if session["step"] > len(STEPS):
        # Registration complete: triage + visit, session closes with END.
        _clear_session(phone_number)
        return _finish_registration(db, phone_number, session["answers"])

    next_step = STEPS[session["step"] - 1]
    return f"CON {next_step['prompt']}"


# --------------------------------------------------------------------------- #
# Main responder
# --------------------------------------------------------------------------- #


def _step(phone_number, db, session, newest):
    """Apply one answer (the newest element of the chain) to the session."""
    if session["step"] == 0:
        # Waiting for the menu choice.
        if newest == "1":
            # One active visit per phone: already-registered patients get
            # their position instead of registering again.
            already = _active_visit_reply(db, phone_number)
            if already is not None:
                reply = already
            else:
                session["step"] = 1
                reply = f"CON {STEPS[0]['prompt']}"
        elif newest == "2":
            reply = _menu_show_position(db, phone_number)
        elif newest == "3":
            reply = _menu_unregister(db, phone_number)
        else:
            reply = f"CON {ERROR_MESSAGE}" + MENU
    else:
        # Mid-registration: apply the newest answer to the current step.
        reply = _advance_registration(db, phone_number, session, newest)

    if reply.startswith("END "):
        _clear_session(phone_number)
    return reply


def _respond(phone_number, answers):
    """Turn the patient's answer chain into a USSD reply.

    Args:
        phone_number: the patient's phone number (from the AT form field).
        answers: ``text.split('*')`` — the whole chain typed so far.
                 Empty list means a brand-new session (show the menu).

    Returns:
        The USSD reply text (always starting with "CON " or "END ").
    """
    if isinstance(answers, str):
        answers = answers.split("*") if answers else []

    chain = "*".join(answers)

    # New session (empty chain): show the menu, drop any stale state.
    if not answers:
        _forget(phone_number)
        return MENU

    newest = answers[-1].strip()

    with get_db() as db:
        # Restart resilience: reload this phone's state from SQLite
        # (no-op while the memory cache is warm).
        _hydrate(db, phone_number)

        # Webhook retry: the exact same chain was replayed — reply identically
        # and do NOT process the answer a second time (no duplicate visits).
        cached = _LAST_REPLY.get(phone_number)
        if cached is not None and cached[0] == chain:
            return cached[1]

        had_session = phone_number in _SESSION
        session = _get_session(phone_number)

        if not had_session and len(answers) > 1:
            # Cold start with a full chain (a brand-new phone replaying every
            # answer at once — the README/curl style): replay each element
            # through the state machine, exactly as the patient walked it.
            reply = MENU
            for element in answers:
                reply = _step(phone_number, db, session, element.strip())
                if reply.startswith("END "):
                    break  # session closed mid-chain: stop (e.g. RED flag)
        else:
            # Normal live flow: only the last element is new.
            reply = _step(phone_number, db, session, newest)

        # Cache for idempotent webhook retries (bounded), then persist.
        if len(_LAST_REPLY) > _SESSION_TTL_CHAINS:
            _LAST_REPLY.clear()
        _LAST_REPLY[phone_number] = (chain, reply)
        _save(db, phone_number, chain, reply)
        return reply
