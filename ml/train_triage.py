"""AFYA SMART — ML triage model training.

Trains a real scikit-learn classifier (GradientBoosting) on a synthetic dataset
generated from WHO IMCI / Tanzanian ETAT-style triage logic — the same clinical
rules that power rules-v1, but with realistic patient noise so the model learns
smooth probabilities instead of hard thresholds.

Outputs:
    ml/models/triage_model.pkl     (joblib artifact)
    ml/models/triage_metadata.json (version, metrics, features)

Run from backend/:
    ../ml/train_triage.py  (or)  .venv/bin/python ../ml/train_triage.py
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, recall_score, confusion_matrix
from sklearn.model_selection import cross_val_score, train_test_split

HERE = Path(__file__).resolve().parent
MODELS_DIR = HERE / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

FEATURES = ["breathing", "conscious", "breathing", "conscious", "bleeding", "fever_days", "pain_level", "risk_group"]

# Uhakika order ni sawa na TRIAGE_QUESTIONS kwenye backend
FEATURES = ["breathing", "conscious", "bleeding", "fever_days", "pain_level", "risk_group"]

LABELS = ["emergency", "urgent", "routine", "self_care"]  # 0,1,2,3

RANDOM_STATE = 42
rng = np.random.default_rng(RANDOM_STATE)

N_SAMPLES = 12000


def generate_case() -> tuple[list[int], int]:
    """Generate one synthetic case: (features, label) kutoka clinical logic + noise."""
    breathing = int(rng.random() < 0.10)      # 10% wana shida ya kupumua (1 = hatari)
    # USSD semantics: 1 = amejiamshi vizuri (NZURI), 0 = hajiamshi (HATARI)
    # 5% hawajiamshi → conscious=0 kwa 5% ya wagonjwa
    conscious = 1 - int(rng.random() < 0.05)
    bleeding = int(rng.random() < 0.08)       # 8% wanatokwa damu nyingi (1 = hatari)

    # Homa: 0=siku1-2, 1=siku3-6, 2=>siku6
    fever_days = int(rng.choice([0, 1, 2], p=[0.55, 0.30, 0.15]))
    # Maumivu: 0=hakuna,1=kidogo,2=kati,3=makali
    pain_level = int(rng.choice([0, 1, 2, 3], p=[0.35, 0.35, 0.20, 0.10]))
    # Kikundi: 0=mzima,1=mjamzito,2=mtoto,3=mzee
    risk_group = int(rng.choice([0, 1, 2, 3], p=[0.55, 0.15, 0.20, 0.10]))

    # ---- Clinical ground-truth logic (WHO IMCI / ETAT inspired, same spirit as rules-v1) ----
    # Hatari: kupumua kwa shida, HAJIAMSHI (conscious=0), damu nyingi
    critical = (breathing == 1) + (conscious == 0) + (bleeding == 1)

    if critical >= 2:
        label = 0  # emergency
    elif critical == 1:
        # dalili moja ya hatari: emergency kama kikundi hatarini, la sivyo urgent
        label = 0 if risk_group >= 1 else 1
    elif fever_days == 2 or pain_level == 3:
        label = 1  # urgent
    elif fever_days == 1 and risk_group >= 2:
        label = 1  # urgent
    elif fever_days >= 1 or pain_level >= 2 or risk_group >= 1:
        label = 2  # routine
    else:
        label = 3  # self_care

    # ---- Noise: wagonjwa halisi hawajibu/kuelekana kikamilifu ----
    # 2% feature noise (misreport)
    for idx in range(6):
        if rng.random() < 0.02:
            if idx in (0, 1, 2):
                features_arr = [breathing, conscious, bleeding]
                features_arr[idx] = 1 - features_arr[idx]
                breathing, conscious, bleeding = features_arr
            else:
                delta = int(rng.choice([-1, 1]))
                val = [fever_days, pain_level, risk_group][idx - 3] + delta
                val = max(0, min(2 if idx == 3 else 3, val))
                if idx == 3:
                    fever_days = val
                elif idx == 4:
                    pain_level = val
                else:
                    risk_group = val

    # 5% label noise: label inayosogezwa class moja juu/chini (mgonjwa/clinician mismatch)
    if rng.random() < 0.05:
        shift = int(rng.choice([-1, 1]))
        label = max(0, min(3, label + shift))

    return [breathing, conscious, bleeding, fever_days, pain_level, risk_group], label


def main() -> None:
    X, y = [], []
    for _ in range(N_SAMPLES):
        feats, label = generate_case()
        X.append(feats)
        y.append(label)

    X = np.array(X)
    y = np.array(y)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=RANDOM_STATE
    )

    models = {
        "gradient_boosting": GradientBoostingClassifier(
            n_estimators=200, max_depth=3, learning_rate=0.1, random_state=RANDOM_STATE
        ),
        "logistic_regression": LogisticRegression(max_iter=1000, random_state=RANDOM_STATE),
    }

    results = {}
    best_name, best_model, best_recall_emergency = None, None, -1.0

    for name, model in models.items():
        model.fit(X_train, y_train)
        y_pred = model.predict(X_test)

        acc = accuracy_score(y_test, y_pred)
        f1m = f1_score(y_test, y_pred, average="macro")
        rec_emergency = recall_score(y_test, y_pred, labels=[0], average="macro", zero_division=0)

        # CV kwa stability
        cv = cross_val_score(model, X_train, y_train, cv=5, scoring="accuracy")

        results[name] = {
            "accuracy": round(float(acc), 4),
            "f1_macro": round(float(f1m), 4),
            "recall_emergency": round(float(rec_emergency), 4),
            "cv_accuracy_mean": round(float(cv.mean()), 4),
            "cv_accuracy_std": round(float(cv.std()), 4),
            "confusion_matrix": confusion_matrix(y_test, y_pred).tolist(),
        }

        # Tunachukua model yenye recall ya emergency bora (zero missed emergencies)
        if rec_emergency > best_recall_emergency:
            best_name, best_model, best_recall_emergency = name, model, rec_emergency

    print("\n=== MODEL COMPARISON ===")
    for name, r in results.items():
        print(f"{name:20s} acc={r['accuracy']:.3f} f1={r['f1_macro']:.3f} "
              f"recall_emergency={r['recall_emergency']:.3f} cv={r['cv_accuracy_mean']:.3f}±{r['cv_accuracy_std']:.3f}")

    print(f"\nWINNER: {best_name} (recall_emergency={best_recall_emergency:.3f})")

    joblib.dump(best_model, MODELS_DIR / "triage_model.pkl")

    metadata = {
        "version": "ml-v1",
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "algorithm": best_name,
        "n_samples": N_SAMPLES,
        "features": FEATURES,
        "labels": LABELS,
        "metrics": results[best_name],
        "all_results": results,
        "data_source": "synthetic — WHO IMCI / Tanzania ETAT triage logic with clinical noise",
    }
    (MODELS_DIR / "triage_metadata.json").write_text(json.dumps(metadata, indent=2))

    print(f"\nSaved: {MODELS_DIR / 'triage_model.pkl'}")
    print(f"Saved: {MODELS_DIR / 'triage_metadata.json'}")
    print("\n=== METADATA ===")
    print(json.dumps(metadata["metrics"], indent=2))


if __name__ == "__main__":
    main()
