"""Afya Smart — rule-based triage.

Returns a triage ``(level, reason)`` pair using only clear, unambiguous rules:

    * **RED** — treat as an emergency right now.
        - loss of consciousness (unresponsive / cannot answer)
        - convulsion during the day
        - chest pain
        - breathing difficulty
        - uncontrolled bleeding
        - infant under 1 year with fever (pre-referral: with only the age in
          years we cannot separate a 2-week-old from a 10-month-old, so the
          safety-first rule refers every young infant with fever)

    * **YELLOW** — should be seen soon (not necessarily an emergency).
        - fever (the reason records how many days it has lasted; 5+ days is
          flagged as prolonged fever)
        - age under 5 OR over 65

    * **GREEN** — routine.

Rule: if in doubt, choose the HIGHER urgency. This is the "safety first"
behaviour: it is always better to escalate a GREEN to YELLOW/RED than to
downgrade a RED to something less urgent.

Every answer also returns a ``reason`` string that explains *why* — this is
the only clinical context we store, and it is never sent out by SMS/USSD.

The rules here are a **prototype** and must be reviewed by medical
professionals before any real use. Read the note in README.md.
"""

from __future__ import annotations

from typing import Tuple

# Sentinel used to mean "the caller did not provide an age at all".  We use
# a unique object (instead of `None`) so a caller can still say age=0 (a
# newborn) without colliding with "no age information".
_NO_AGE = object()

# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #

def triage(symptoms: dict) -> Tuple[str, str]:
    """Rule-based triage.

    Args:
        symptoms: mapping of symptom key -> normalised value, e.g.::

            {"chest_pain": True, "age": 30}

    Returns:
        (level, reason) where ``level`` is one of "RED", "YELLOW", "GREEN".
        ``reason`` always explains the decision.
    """
    # Normalise: every value is coerced to a real boolean so a missing key,
    # an empty string, or the string "false" can never accidentally become True.
    has_chest_pain = _as_bool(symptoms.get("chest_pain"))
    has_breathing_difficulty = _as_bool(symptoms.get("breathing_difficulty"))
    has_severe_bleeding = _as_bool(symptoms.get("severe_bleeding"))
    has_loss_of_consciousness = _as_bool(symptoms.get("loss_of_consciousness"))
    has_convulsion = _as_bool(symptoms.get("convulsion"))
    has_fever = _as_bool(symptoms.get("fever"))

    # How many days the fever has lasted (asked only when there is fever).
    # A missing/invalid value simply means "unknown" — it never escalates
    # on its own, it only enriches the reason.
    try:
        fever_days = int(symptoms.get("fever_days"))
    except (TypeError, ValueError):
        fever_days = None

    # Age (integer years). A missing key, None, or a non-numeric value means
    # "we do not know the age" and is treated as NOT a child/elder. 0 means
    # "the patient is an infant under one year old" (age < 5).
    age = symptoms.get("age", _NO_AGE)
    try:
        age = int(age)
    except (TypeError, ValueError):
        age = _NO_AGE

    # Safety first: when we are unsure we climb the urgency ladder.
    reason_parts: list[str] = []

    # --- RED: emergencies -------------------------------------------------
    if has_chest_pain:
        reason_parts.append("chest pain")
    if has_breathing_difficulty:
        reason_parts.append("breathing difficulty")
    if has_severe_bleeding:
        reason_parts.append("severe bleeding")
    if has_loss_of_consciousness:
        reason_parts.append("unconsciousness")
    if has_convulsion:
        reason_parts.append("convulsion")
    # A baby under one year with fever needs pre-referral (IMCI: young
    # infants with fever are referred urgently).
    if has_fever and age != _NO_AGE and age < 1:
        reason_parts.append("infant with fever")

    if reason_parts:
        return "RED", "EMERGENCY - " + ", ".join(reason_parts)

    # --- YELLOW: risk groups ---------------------------------------------
    if has_fever:
        reason_parts.append("fever")
        # Fever that will not go away (5+ days) is its own warning sign.
        if fever_days is not None and fever_days >= 5:
            reason_parts.append("prolonged fever (5+ days)")
    if age != _NO_AGE and (age < 5 or age > 65):
        reason_parts.append("age < 5 or > 65")

    if reason_parts:
        return "YELLOW", "WATCH - " + ", ".join(reason_parts)

    # --- GREEN: routine ---------------------------------------------------
    return "GREEN", "ROUTINE - no emergency features found"


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _as_bool(value: object) -> bool:
    """Coerce a USSD/API value into a real boolean.

    USSD comes in as strings ("1", "true", "yes", "0", ...).  Anything that
    *looks* like a truthy affirmative becomes True; an explicit falsy or a
    missing value becomes False.  This table is exhaustive so beginners can
    see exactly what maps to what.
    """
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "on", "t", "yup", "da"}:  # "da" = yes in some African languages
        return True
    if text in {"0", "false", "no", "n", "off", "f", "nope", "null", "none", ""}:
        return False
    # Anything unexpected (e.g. the word "maybe") is treated as UNSURE -> the
    # triage function will escalate to a higher urgency.
    return True
