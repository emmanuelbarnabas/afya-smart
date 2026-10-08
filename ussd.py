"""Afya Smart — USSD entry point (the patient-facing channel).

This is the only file a patient (or a nurse testing the flow from a phone)
will ever touch.  It follows the Africa's Talking USSD protocol:

    * Africa's Talking POSTs form fields (phoneNumber, text, sessionId, ...).
    * ``text`` is a chain of answers, each answer appended with a ``*``.
        - first answer: "1"      -> sex question
        - second:       "1*0"    -> sex=0 then fever=1
        - third:        "1*0*1"  -> sex=0, fever=1, age=0
    * Every reply must start with "CON " (keep the session open) or "END "
      (close the session).

There is exactly one active visit per phone number: if a patient has already
registered (their visit is still waiting / called / in consult / pending) they
are told to use their queue position instead of registering again.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Optional

from flask import request

from app import get_db, init_db
from triage import triage

# --------------------------------------------------------------------------- #
# USSD strings (Kiswahili)
# --------------------------------------------------------------------------- #

# Every message ends with a newline so Africa's Talking renders each line as a
# separate screen.  The session stays open until we send "END ".
MENU = (
    "CON CHAGUA HUDUMA:\n"
    "1. Kuangalia dalili zako (triage)\n"
    "2. Kufikia nafasi yako kwenye foleni\n"
    "3. Ondoa msajili\n"
)

QUESTION_SEX = "GUNWANA WA MTO: 1=Bwana 2=Bibi 3=Hatua yoyote\n"
QUESTION_FEVER = "Je, una homa? 1=Ndiyo 2=Hapana\n"
QUESTION_AGE = "Kipindi chako cha umri (miaka): kwa mfano 3 au 40\n"
QUESTION_CHEST = "Je, una moyo mrefu au maumivu ya mfuko? 1=Ndiyo 2=Hapana\n"
QUESTION_BREATH = "Je, una kupumua kwa shida? 1=Ndiyo 2=Hapana\n"
QUESTION_BLEED = "Je, kuna damu ya kupita kiasi? 1=Ndiyo 2=Hapana\n"

QUESTION_FACILITY = "Hii ni kituo gani? 1=Msasani 2=Kapoleni 3=Je, unachouonekana\n"

# RED (emergency) reply -- tells the patient to go to the hospital NOW.  No
# queue slot is given because the patient must not wait in line.
RED_MESSAGE = (
    "END Bahati gracious - hii ni dharura!\n"
    "Mgonjwa afike kituo cha afya HADI au wodi ya dharura.\n"
    "Kama hauna uwezo wa kumpeleka, piga 112.\n"
    "Hakikisha ugae nyumbani kabla ya kuenda.\n"
)

ERROR_MESSAGE = "Jibu si sahihi. Nambure karatasi tena.\n"

INVALID_AGE_MESSAGE = "CON Jambo, umri uliyotoa haufai sahihi. Nambure karatasi tena.\n"

SUCCES_NAFASI_MESSAGE = "Nafasi yako kwenye foleni ni #{position}."

# --------------------------------------------------------------------------- #
# Small "database" helpers (Flask + SQLite)
# --------------------------------------------------------------------------- #

def _get_patient(db, phone_number):
    """Return the patient with this phone number (None if not found)."""
    cur = db.execute("SELECT * FROM patients WHERE phone_number = ?", (phone_number,))
    row = cur.fetchone()
    return row


def _patient_has_active_visit(db, phone_number):
    """A patient has an active visit when their latest visit is not finished."""
    cur = db.execute(
        """
        SELECT v.id
        FROM visits v
        JOIN patients p ON p.id = v.patient_id
        WHERE p.phone_number = ?
          AND v.status != 'finished'
        ORDER BY v.joined_at DESC
        LIMIT 1
        """,
        (phone_number,),
    )
    return cur.fetchone() is not None


def _create_visit(db, patient_id, level, reason):
    """Record a new visit. Returns the row id."""
    cur = db.execute(
        """
        INSERT INTO visits (patient_id, level, reason)
        VALUES (?, ?, ?)
        """,
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


# --------------------------------------------------------------------------- #
# User-facing helpers
# --------------------------------------------------------------------------- #

def _respond(phone_number, answers):
    """Main dispatch: turn the patient's answers into a USSD reply.

    Args:
        phone_number: the patient's phone number (from the AT form field).
        answers: list of strings the patient has typed so far, e.g. ["1", "2"].

    Returns the USSD reply text (starting with "CON " or "END ").
    """
    with get_db() as db:
        # One active visit per phone: if the patient is already being served,
        # do not let them register again.  Instead, tell them their position.
        if _patient_has_active_visit(db, phone_number):
            return f"END Ungoa viungo vya simu. Unaweza kufikia nafasi yako:\nSUBIKISHE KWA KIPIMO CHANGAMO\n"

        # No active visit -> register as normal.
        return _register_from_answers(db, phone_number, answers)


def _register_from_answers(db, phone_number, answers):
    """Walk through the registration questions one by one."""
    # answers is a list of strings like ["1", "2", "3", ...].
    # We only look at the LAST answer (Africa's Talking appends one per screen
    # and then replays the whole chain).
    last = answers[-1] if answers else ""

    if not last:
        # First ever question: sex.
        return MENU

    # ------------------------------------------------------------------
    # 1. Sex
    # ------------------------------------------------------------------
    if len(answers) == 1:
        if last == "1":
            return QUESTION_SEX
        if last == "2":
            return QUESTION_SEX
        return INVALID_AGE_MESSAGE

    # ------------------------------------------------------------------
    # 2. Fever
    # ------------------------------------------------------------------
    if len(answers) == 2:
        if last == "1":
            return QUESTION_FEVER
        if last == "2":
            return QUESTION_FEVER
        return INVALID_AGE_MESSAGE

    # ------------------------------------------------------------------
    # 3. Age
    # ------------------------------------------------------------------
    if len(answers) == 3:
        # Keep it simple: age is a number.  Reject anything that is not a
        # small positive integer so non-numeric input (a disease name in
        # SMS/USSD) never crashes the session.
        age_text = last.strip()
        if not age_text.isdigit() or int(age_text) <= 0:
            return INVALID_AGE_MESSAGE
        # Only advance if the age is valid.  We do NOT advance when the
        # answer is invalid -- the patient stays on this screen.
        age = int(age_text)
        return QUESTION_CHEST

    # ------------------------------------------------------------------
    # 4. Chest pain
    # ------------------------------------------------------------------
    if len(answers) == 4:
        if last == "1":
            return QUESTION_BREATH
        if last == "2":
            return QUESTION_BREATH
        return INVALID_AGE_MESSAGE

    # ------------------------------------------------------------------
    # 5. Breathing difficulty
    # ------------------------------------------------------------------
    if len(answers) == 5:
        if last == "1":
            return QUESTION_BLEED
        if last == "2":
            return QUESTION_BLEED
        return INVALID_AGE_MESSAGE

    # ------------------------------------------------------------------
    # 6. Severe bleeding
    # ------------------------------------------------------------------
    if len(answers) == 6:
        if last == "1":
            return QUESTION_FACILITY
        if last == "2":
            return QUESTION_FACILITY
        return INVALID_AGE_MESSAGE

    # ------------------------------------------------------------------
    # 7. Facility
    # ------------------------------------------------------------------
    if len(answers) == 7:
        # Every numeric answer must be a real integer.  If any of them is not
        # (e.g. a disease name typed in SMS/USSD), we refuse and ask the user
        # to repeat.  This keeps USSD from crashing on garbage input.
        numeric = True
        for i in range(1, 7):
            token = answers[i].strip()
            if not token.isdigit() or int(token) < 0:
                numeric = False
                break
        if not numeric:
            return INVALID_AGE_MESSAGE

        facility = _resolve_facility(db, last)
        if facility is None:
            return INVALID_AGE_MESSAGE

        # Build a tidy dictionary of the answers *in order*.
        sex = None if len(answers) < 2 else int(answers[1])
        fever = None if len(answers) < 3 else int(answers[2])
        age = None if len(answers) < 4 else int(answers[3])
        chest = None if len(answers) < 5 else int(answers[4])
        breath = None if len(answers) < 6 else int(answers[5])
        bleed = None if len(answers) < 7 else int(answers[6])

        level, reason = triage(
            {
                "chest_pain": chest == 1,
                "breathing_difficulty": breath == 1,
                "severe_bleeding": bleed == 1,
                "fever": fever == 1,
                "age": age,
            }
        )

        # Record the visit (RED and non-RED are logged the same way).
        pid = _patient_id(db, phone_number)
        _create_visit(db, pid, level, reason)
        _log_audit(db, "ussd", "register", "visits", pid, reason)

        if level == "RED":
            # RED patients go straight to the hospital.  No queue number.
            return RED_MESSAGE

        # Non-RED patients get a queue number and an estimated wait.  We do
        # not store queue numbers in the SQLite version; we just acknowledge.
        return (
            f"END Unafikia nafasi ya {hash(phone_number) % 1000:03d}.\n"
            f"Huduma yako inaanza Sasa.\n"
        )

    # ------------------------------------------------------------------
    # Should never reach here.
    # ------------------------------------------------------------------
    return ERROR_MESSAGE


def _resolve_facility(db, choice):
    """Map a facility choice string to a facility id."""
    if choice == "1":
        return 1
    if choice == "2":
        return 2
    if choice == "3":
        return 3
    return None


def _get_form_value(form, key, default=""):
    """Read one Africa's Talking form field, returning a string."""
    value = form.get(key, default)
    return value if isinstance(value, str) else str(value)


def _patient_id(db, phone_number):
    """Get or create a patient record for this phone number."""
    row = _get_patient(db, phone_number)
    if row is not None:
        return row["id"]
    cur = db.execute(
        """
        INSERT INTO patients (phone_number, full_name)
        VALUES (?, ?)
        """,
        (phone_number, "Mgonjwa (USSD)"),
    )
    db.commit()
    return cur.lastrowid
