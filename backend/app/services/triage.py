"""Triage service — ML model (ml-v2) na rules engine (rules-v2) kama fallback.

Model halisi ya scikit-learn (GradientBoosting) ndiyo inaamua; rules-v2 (WHO
IMCI / ETAT-inspired) ni fallback pale model haipo, haihakiki, au pale dalili
ni za hatari (safety override — zero missed emergencies).

rules-v2 nyongeza ya uhalisia ikilinganishwa na v1:
  * Homa ya zaidi ya siku 6 kwa mtoto/mzee/mjamzito ni hatari zaidi
    (IMCI: "fever for ≥ 7 days" ni sign ya hatari).
  * Maumivu makali + kikundi hatarini (mjamzito/mtoto/mzee) huinua urgency.
  * URGENT haulazimiki kufuata foleni — anapewa kipaumbele cha HARAKA.

Kumbuka kwa semantics ya USSD: kwa "conscious", jibu 1 = amejiamshi vizuri
(HALI NZURI); 0 = hajiamshi (HATARI). Kwa breathing/bleeding, 1 = dalili
ya hatari. Angalia ml/train_triage.py kwa dataset encoding.
"""
from __future__ import annotations

from app.models.triage import UrgencyLevel

# Maswali ya triage (Kiswahili) — yanatumika USSD na kuhifadhiwa kwenye session.
# Maswali 6 tu: USSD session ya AT ina mwisho wa muda, kila swali ni screen.
TRIAGE_QUESTIONS: list[dict] = [
    {
        "key": "breathing",
        "prompt": "Je, mgonjwa anapumua kwa shida kupita kawaida? 1=Ndiyo 0=Hapana",
        "options": {"1": True, "0": False},
    },
    {
        "key": "conscious",
        "prompt": "Je, mgonjwa yuko fahamu (anatambua na anazungumza)? 1=Ndiyo 0=Hapana",
        "options": {"1": True, "0": False},
    },
    {
        "key": "bleeding",
        "prompt": "Je, kuna sehemu inayotokwa damu nyingi bila kushikwa? 1=Ndiyo 0=Hapana",
        "options": {"1": True, "0": False},
    },
    {
        "key": "fever_days",
        "prompt": "Homa imekuwepo siku ngapi? 0=Siku 1-2 1=Siku 3-6 2=Zaidi ya siku 6",
        "options": {"0": 0, "1": 1, "2": 2},
    },
    {
        "key": "pain_level",
        "prompt": "Maumivu ni ya kiwango gani? 0=Hakuna 1=Kidogo 2=Kati kati 3=Makali",
        "options": {"0": 0, "1": 1, "2": 2, "3": 3},
    },
    {
        "key": "risk_group",
        "prompt": "Mgonjwa ni nani? 0=Mtu mzima 1=Mjamzito 2=Mtoto (chini ya miaka 5) 3=Mzee (miaka 60+)",
        "options": {"0": 0, "1": 1, "2": 2, "3": 3},
    },
]

# Kanuni za maswali ya dharura: key → value inayomaanisha dalili ya hatari.
# Kwa "conscious", 0 (hajiamshi) NDIYO hatari — jibu 1 (amejiamshi) ni hali nzuri.
_CRITICAL_RULES: dict[str, bool] = {
    "breathing": True,   # 1 = anashindwa kupumua → hatari
    "conscious": False,  # 0 = hajiamshi → hatari
    "bleeding": True,    # 1 = damu nyingi → hatari
}

MODEL_VERSION = "rules-v2"


def classify_rules(answers: dict) -> tuple[UrgencyLevel, float]:
    """Rules engine (rules-v2) — fallback ya ML; pia inatumika na ml_triage safety.

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

    # EMERGENCY: dalili ya moja kwa moja ya hatari ya maisha (ETAT emergency signs)
    if critical_flags >= 2:
        return UrgencyLevel.EMERGENCY, 0.95
    if critical_flags == 1:
        # Dalili moja ya hatari + kikundi hatarini → emergency; vinginevyo urgent
        if risk >= 1:
            return UrgencyLevel.EMERGENCY, 0.80
        return UrgencyLevel.URGENT, 0.75

    # RED-FLAG COMBOS (v2): hakuna dalili moja kwa moja, lakini mchanganyiko ni hatari
    # Homa ya muda mrefu (> siku 6) kwa mjamzito/mtoto/mzee au na maumivu makali
    if fever >= 2 and (risk >= 1 or pain >= 3):
        return UrgencyLevel.URGENT, 0.72
    # URGENT: maumivu makali, au homa ya muda mrefu, au homa + kikundi hatarini
    if pain >= 3:
        return UrgencyLevel.URGENT, 0.70
    if fever >= 2:
        return UrgencyLevel.URGENT, 0.68
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
    """Return (urgency, confidence) — DELEGATES kwa ML model halisi (ml-v2)."""
    urgency, confidence, _version = classify_full(answers)
    return urgency, confidence


def parse_answer(question: dict, raw: str) -> object:
    """Badilisha jibu la USSD (string) kuwa value ya kweli; return None kama si sahihi."""
    option = question.get("options", {}).get(raw.strip())
    return option


def outcome_for_urgency(urgency: UrgencyLevel) -> str:
    """Outcome kwa kila kiwango cha urgency (analytics stream).

    URGENT → walk_in_directed: mgonjwa anaagizwa afike sasa hivi na anawekwa
    foleni yenye kipaumbele; hii inatofautishwa na EMERGENCY (dharura tupu)
    ili analytics ionyeshe nguvu ya mfumo kwa kila mtiririko.
    """
    return {
        UrgencyLevel.EMERGENCY: "emergency_directed",
        UrgencyLevel.URGENT: "walk_in_directed",
        UrgencyLevel.ROUTINE: "slot_booked",
        UrgencyLevel.SELF_CARE: "self_care_given",
    }[urgency]


def message_for_urgency(urgency: UrgencyLevel, facility_name: str = "kituo cha afya", queue_pos: int | None = None) -> str:
    """Ujumbe wa Kiswahili kwa mgonjwa — unaelekeza kwa vitendo, una salio la usalama."""
    if urgency == UrgencyLevel.EMERGENCY:
        return (
            "DHARURA! Mgonjwa afike kituo cha afya MARA MOJA au wodi ya dharura. "
            "Kama hapana uwezo wa kumpeleka, piga 112. Usisubiri foleni."
        )
    if urgency == UrgencyLevel.URGENT:
        pos = f" Nafasi yako: #{queue_pos}." if queue_pos else ""
        return (
            f"Hali inahitaji ukaguzi wa haraka LEO. Fika {facility_name} sai hivi.{pos} "
            "Atapewa kipaumbele. Kama hali ibadilike ghafla, piga 112."
        )
    if urgency == UrgencyLevel.ROUTINE:
        return (
            "Hali inaweza kupangwa kwa miadi. Chagua saa unayopenda kwenye menyu "
            "ijayo; utapokea SMS ya uthibitisho."
        )
    return (
        "Dalili zinaweza kushughulikiwa nyumbani: pumzika, kunywa maji mengi. "
        "Kama dalili zinazidi siku 3 au zikaongezeka, rudi kituoni au piga "
        "namba ya huduma tena."
    )
