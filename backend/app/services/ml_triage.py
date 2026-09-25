"""ML triage inference — model halisi (ml-v1) juu ya rules engine.

Model: GradientBoosting iliyofundishwa kwenye dataset ya sintetiki ya WHO IMCI /
ETAT triage logic (angalia ml/train_triage.py). Wrapper hii inahakikisha:

1. **Zero missed emergencies** — safety override ya kliniki: dalili za hatari
   (kupumua kwa shida, hajiamshi, damu nyingi) zinapanda hadi EMERGENCY hata
   kama model ingesema vinginevyo.
2. **Uncertainty → rules fallback** — kama model haina uhakika (confidence < 0.5),
   tunarudi kwenye rules-v1 (deterministic, clinically vetted).
3. **Model haipo/wameharibika → rules fallback** — mfumo hauvunjiki.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from app.models.triage import UrgencyLevel
from app.services.triage import classify_rules as rules_classify
from app.services.triage import MODEL_VERSION as RULES_VERSION

logger = logging.getLogger("afyasmart.ml_triage")

# Order lazima iwe sawa na TRAINING FEATURES:
# [breathing, conscious, bleeding, fever_days, pain_level, risk_group]
_FEATURE_ORDER = ["breathing", "conscious", "bleeding", "fever_days", "pain_level", "risk_group"]
_LABELS = [UrgencyLevel.EMERGENCY, UrgencyLevel.URGENT, UrgencyLevel.ROUTINE, UrgencyLevel.SELF_CARE]

_CONFIDENCE_FLOOR = 0.5  # chini ya hii → rules fallback

# Dalili za hatari ya maisha. USSD semantics:
#   breathing=1 → hatari | conscious=0 → hatari (0 = HAJIAMSHI) | bleeding=1 → hatari
# (kwenye feature vector, conscious imetumwa kama True/False → 1/0;
#  hatari = conscious == 0)
_CRITICAL_FLAG_VALUES = {"breathing": 1, "conscious": 0, "bleeding": 1}


def _resolve_model_path() -> Path | None:
    from app.core.config import settings

    candidates = [
        Path(settings.triage_model_path),
        Path("../ml/models/triage_model.pkl"),
        Path("ml/models/triage_model.pkl"),
        Path(__file__).resolve().parents[3] / "ml" / "models" / "triage_model.pkl",
    ]
    for p in candidates:
        if p.is_file():
            return p
    return None


class _ModelHolder:
    """Lazy singleton — model inaload mara moja tu, error inarudisha None."""

    def __init__(self) -> None:
        self.model = None
        self.metadata: dict = {}
        self.load_error: str | None = None
        self._loaded = False

    def _load(self) -> None:
        self._loaded = True
        path = _resolve_model_path()
        if path is None:
            self.load_error = "model artifact not found"
            return
        try:
            import joblib

            self.model = joblib.load(path)
            meta_path = path.parent / "triage_metadata.json"
            if meta_path.is_file():
                self.metadata = json.loads(meta_path.read_text())
            logger.info("ML triage model loaded: %s (%s)", path, self.metadata.get("algorithm"))
        except Exception as exc:  # noqa: BLE001
            self.model = None
            self.load_error = str(exc)
            logger.warning("Imeshindikana kupakia triage model: %s", exc)

    def get(self):
        if not self._loaded:
            self._load()
        return self.model


_holder = _ModelHolder()


def get_model_info() -> dict | None:
    """Taarifa za model kwa /health na dashboard (haiwezi crash API)."""
    try:
        model = _holder.get()
    except Exception:  # noqa: BLE001
        return None
    if model is None:
        return {
            "loaded": False,
            "version": RULES_VERSION,
            "error": _holder.load_error,
        }
    metrics = _holder.metadata.get("metrics", {})
    return {
        "loaded": True,
        "version": _holder.metadata.get("version", "ml-v1"),
        "algorithm": _holder.metadata.get("algorithm"),
        "trained_at": _holder.metadata.get("trained_at"),
        "accuracy": metrics.get("accuracy"),
        "recall_emergency": metrics.get("recall_emergency"),
        "n_samples": _holder.metadata.get("n_samples"),
    }


# Default ya feature isijulikani (None) = hali "nzuri" — sawa na rules-v1 ambako
# jibu lisilopo halisababishi critical flag (conscious=None → amejiamshi assumption).
_FEATURE_DEFAULTS = {
    "breathing": 0,
    "conscious": 1,
    "bleeding": 0,
    "fever_days": 0,
    "pain_level": 0,
    "risk_group": 0,
}


def _answers_to_vector(answers: dict) -> list[int]:
    """{question_key: value} → [int features] kwa order ya training."""
    vec = []
    for key in _FEATURE_ORDER:
        value = answers.get(key)
        if value is None:
            value = _FEATURE_DEFAULTS[key]
        vec.append(int(bool(value)) if isinstance(value, bool) else int(value))
    return vec


def _critical_flags(features: list[int]) -> int:
    return sum(1 for i, key in enumerate(_FEATURE_ORDER[:3]) if features[i] == _CRITICAL_FLAG_VALUES[key])


def _apply_safety_override(pred_idx: int, features: list[int]) -> tuple[int, UrgencyLevel, str | None]:
    """Zero missed emergencies: kliniki inashinda model pale dalili ni za hatari.

    Returns (final_idx, urgency, reason) — reason si None kama override imetumika.
    """
    flags = _critical_flags(features)
    risk = features[5]

    if flags >= 2:
        return 0, UrgencyLevel.EMERGENCY, "safety_override: critical flags >= 2"
    if flags == 1 and risk >= 1:
        return 0, UrgencyLevel.EMERGENCY, "safety_override: critical + risk group"
    if flags == 1 and pred_idx > 1:  # model ilisema routine/self_care →panda hadi urgent
        return 1, UrgencyLevel.URGENT, "safety_override: critical flag escalated to urgent"
    return pred_idx, _LABELS[pred_idx], None


def classify(answers: dict) -> tuple[UrgencyLevel, float, str]:
    """ML triage: return (urgency, confidence 0-1, model_version).

    - Model ipo + confident → ml-v1 prediction
    - Model haipo / confidence < 0.5 → rules-v1 fallback
    - Dalili za hatari → safety override (ml-v1 + override)
    """
    model = _holder.get()

    # --- Fallback: model haipo ---
    if model is None:
        urgency, conf = rules_classify(answers)
        return urgency, conf, RULES_VERSION

    features = _answers_to_vector(answers)

    # --- Fallback: hakuna jibu lolote (safety default ya rules) ---
    if not any(answers.get(k) is not None for k in _FEATURE_ORDER):
        urgency, conf = rules_classify({})
        return urgency, conf, RULES_VERSION

    try:
        probs = model.predict_proba([features])[0]
    except Exception:  # noqa: BLE001
        logger.exception("ML inference imeshindikana — rules fallback")
        urgency, conf = rules_classify(answers)
        return urgency, conf, RULES_VERSION

    pred_idx = int(probs.argmax())
    confidence = float(probs[pred_idx])

    pred_idx, urgency, override_reason = _apply_safety_override(pred_idx, features)
    if override_reason:
        logger.info("%s (features=%s)", override_reason, features)
        # Confidence ya uamuzi wa override ni ya kliniki (rules), sio ya model
        # iliyokataa — tunachukua max ya mbili (uwazi kwa mwanajaji/m clinicians).
        r_urgency, r_conf = rules_classify(answers)
        return urgency, round(max(r_conf, confidence), 3), "ml-v1+safety"

    # --- Fallback: model haihakiki ---
    if confidence < _CONFIDENCE_FLOOR:
        r_urgency, r_conf = rules_classify(answers)
        # Chagua uamuzi wa kinaseza kwa usalama (class ya juu zaidi)
        if _LABELS.index(r_urgency) < pred_idx:
            return r_urgency, round(r_conf, 3), RULES_VERSION
        return urgency, round(confidence, 3), "ml-v1"

    return urgency, round(confidence, 3), "ml-v1"
