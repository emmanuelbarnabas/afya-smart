"""Triage service — ML model (ml-v1) na rules engine (rules-v1) kama fallback.

Model halisi ya scikit-learn (GradientBoosting) ndiyo inaamua; rules-v1 (WHO
IMCI / ETAT-inspired) ni fallback pale model haipo, haihakiki, au pale dalili
ni za hatari (safety override — zero missed emergencies).

Kumbuka kwa semantics ya USSD: kwa "conscious", jibu 1 = amejiamshi vizuri
(HALI NZURI); 0 = hajiamshi (HATARI). Kwa breathing/bleeding, 1 = dalili
ya hatari. Angalia ml/train_triage.py kwa dataset encoding.
"""
from __future__ import annotations

from app.models.triage import UrgencyLevel

# Maswali ya triage (Kiswahili) — yanatumika USSD na kuhifadhiwa kwenye session
TRIAGE_QUESTIONS: list[dict] = [
    {
        "key": "breathing",
        "prompt": "Je, mgonjwa ana shida ya kupumua? 1=Ndiyo 0=Hapana",
        "options": {"1": True, "0": False},
    },
    {
        "key": "conscious",
        "prompt": "Je, mgonjwa yu hai na amejiamsha vizuri? 1=Ndiyo 0=Hapana",
        "options": {"1": True, "0": False},
    },
    {
        "key": "bleeding",
        "prompt": "Je, kuna damu nyingi inayotokwa? 1=Ndiyo 0=Hapana",
        "options": {"1": True, "0": False},
    },
    {
        "key": "fever_days",
        "prompt": "Je, homa imekuwepo siku ngapi? 0=Siku 1-2 1=Siku 3-6 2=Zaidi ya siku 6",
        "options": {"0": 0, "1": 1, "2": 2},
    },
    {
        "key": "pain_level",
        "prompt": "Je, maumivu ni ya kiwango gani (0-10)? 0=Hakuna 1=Kidogo 2=Kati 3=Makali",
        "options": {"0": 0, "1": 1, "2": 2, "3": 3},
    },
    {
        "key": "risk_group",
        "prompt": "Je, mgonjwa ni: 0=Mtu mzima wa kawaida 1=Mjamzito 2=Mtoto(chini ya miaka 5) 3=Mzee(60+)",
        "options": {"0": 0, "1": 1, "2": 2, "3": 3},
    },
]

# Kanuni za maswali ya dharura: key → value inayomaanisha dalili ya hatari.
# Kwa "conscious", 0 (hajiamshi) NDIYO hatari — jibu 1 (amejiamshi) ni hali nzuri.
_CRITICAL_RULES: dict[str, bool] = {
    "breathing": True,   # 1 = ana shida ya kupumua → hatari
    "conscious": False,  # 0 = hajiamshi → hatari
    "bleeding": True,    # 1 = damu nyingi → hatari
}

MODEL_VERSION = "rules-v1"


def classify_rules(answers: dict) -> tuple[UrgencyLevel, float]:
    """Rules engine (rules-v1) — fallback ya ML; pia inatumika na ml_triage safety.

    Majibu yanatarajiwa kama {question_key: value} kama ilivyorudishwa na
    ``parse_answer``. Shaka (answer isiyojulikana) inapeleka urgency juu.
    """
    if not answers:
        # Hakuna taarifa — hatua salama ni kuomba mgonjwa afike facility
        return UrgencyLevel.URGENT, 0.3

    critical_flags = 0
    for key, danger_value in _CRITICAL_RULES.items():
        value = answers.get(key)
        if value is danger_value:
            critical_flags += 1

    fever = answers.get("fever_days") or 0
    pain = answers.get("pain_level") or 0
    risk = answers.get("risk_group") or 0

    # EMERGENCY: dalili ya moja kwa moja ya hatari ya maisha
    if critical_flags >= 2:
        return UrgencyLevel.EMERGENCY, 0.95
    if critical_flags == 1:
        # Dalili moja ya hatari + kikundi hatarini → emergency; vinginevyo urgent
        if risk >= 1:
            return UrgencyLevel.EMERGENCY, 0.80
        return UrgencyLevel.URGENT, 0.75

    # URGENT: homa ya muda mrefu, maumivu makali, au kikundi hatarini
    if fever >= 2 or pain >= 3:
        return UrgencyLevel.URGENT, 0.70
    if fever == 1 and risk >= 2:
        return UrgencyLevel.URGENT, 0.65

    # ROUTINE: dalili za kawaida zinazohitaji huduma siku hiyo au kesho
    if fever >= 1 or pain >= 2 or risk >= 1:
        return UrgencyLevel.ROUTINE, 0.60

    # SELF_CARE: hakuna dalili kubwa
    return UrgencyLevel.SELF_CARE, 0.55


def classify_full(answers: dict) -> tuple[UrgencyLevel, float, str]:
    """Return (urgency, confidence, model_version) — version halisi ya model iliyotumika."""
    from app.services.ml_triage import classify as ml_classify

    return ml_classify(answers)


def classify(answers: dict) -> tuple[UrgencyLevel, float]:
    """Return (urgency, confidence) — DELEGATES kwa ML model halisi (ml-v1)."""
    urgency, confidence, _version = classify_full(answers)
    return urgency, confidence


def parse_answer(question: dict, raw: str) -> object:
    """Badilisha jibu la USSD (string) kuwa value ya kweli; return None kama si sahihi."""
    option = question.get("options", {}).get(raw.strip())
    return option


def outcome_for_urgency(urgency: UrgencyLevel) -> str:
    """Default outcome kwa kila kiwango cha urgency (kabla ya user kubook slot)."""
    return {
        UrgencyLevel.EMERGENCY: "emergency_directed",
        UrgencyLevel.URGENT: "emergency_directed",
        UrgencyLevel.ROUTINE: "slot_booked",
        UrgencyLevel.SELF_CARE: "self_care_given",
    }[urgency]


def message_for_urgency(urgency: UrgencyLevel, facility_name: str = "kituo cha afya") -> str:
    """Ujumbe wa Kiswahili kwa mgonjwa kulingana na matokeo ya triage."""
    return {
        UrgencyLevel.EMERGENCY: (
            "DHARURA! Nenda kituo cha afya mara moja au piga 199. "
            "Usisubiri mfumo wa foleni."
        ),
        UrgencyLevel.URGENT: (
            f"Hitaji la ukaguzi wa haraka leo. Nenda {facility_name} leo — "
            "ukifikaomba ukaguzi wa dharura."
        ),
        UrgencyLevel.ROUTINE: (
            "Hali yako inaweza kupangwa kwa miadi. Tafadhali chagua saa "
            "unaopenda kwenye menyu ijayo."
        ),
        UrgencyLevel.SELF_CARE: (
            "Hali yako inaweza kushughulikiwa nyumbani. Pumzisha, kunywa maji, "
            "na uende kituoni ikiwa inazidi kuwa mbaya."
        ),
    }[urgency]
