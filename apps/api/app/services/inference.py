"""ML inference service: load_models(model_dir) once at startup and score_case(features)."""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import joblib
from ml.train.calibrate import predict_calibrated
from ml.train.explain import build_tree_explainer, explain_single_case
from ml.train.features import encode_single_case
from ml.train.train_cox import score_survival_single
from sqlalchemy.orm import Session

from app.db.models import RiskScore

logger = logging.getLogger(__name__)

_MODEL_CACHE: dict[str, Any] = {}


class ModelArtifactsMissingError(RuntimeError):
    """Raised when required trained ML artifacts are missing from model_dir."""


def load_models(model_dir: Path | str) -> dict[str, Any]:
    """Load trained XGBoost, isotonic calibrator, Cox/AFT bundle, and model_version once."""
    mdir = Path(model_dir)
    required = ("model_version.txt", "xgb.joblib", "calibrator.joblib", "cox.joblib")
    missing = [name for name in required if not (mdir / name).exists()]
    if missing:
        raise ModelArtifactsMissingError(
            f"Missing trained ML artifacts in {mdir}: {', '.join(missing)}. "
            "Run `uv run python ../../ml/train/evaluate.py` first."
        )

    xgb_model = joblib.load(mdir / "xgb.joblib")
    calibrator = joblib.load(mdir / "calibrator.joblib")
    cox_bundle = joblib.load(mdir / "cox.joblib")
    version = (mdir / "model_version.txt").read_text(encoding="utf-8").strip()
    explainer = build_tree_explainer(xgb_model)

    metrics_path = mdir / "metrics.json"
    metrics_data = (
        json.loads(metrics_path.read_text(encoding="utf-8"))
        if metrics_path.exists()
        else {}
    )

    bundle = {
        "xgb": xgb_model,
        "calibrator": calibrator,
        "cox": cox_bundle,
        "explainer": explainer,
        "model_version": version,
        "km_curve": cox_bundle.get("km_curve", []),
        "metrics": metrics_data,
    }
    _MODEL_CACHE.clear()
    _MODEL_CACHE.update(bundle)
    logger.info("loaded ML artifacts", extra={"model_version": version, "dir": str(mdir)})
    return bundle


def get_loaded_models(model_dir: Path | str | None = None) -> dict[str, Any]:
    """Return cached models, loading from model_dir if not yet initialized."""
    if not _MODEL_CACHE:
        if model_dir is None:
            from app.core.config import get_settings

            model_dir = get_settings().model_dir
        return load_models(model_dir)
    return _MODEL_CACHE


def build_case_feature_dict(c: Any, pat: Any, days_in_stage: float = 0.1) -> dict[str, Any]:
    """Assemble the canonical 17-feature vector from a Case and Patient ORM row."""
    return {
        "screening_type": c.screening_type,
        "severity_grade": c.severity_grade,
        "urgent_flag": 1 if c.urgency_tier == 1 else 0,
        "finding_to_order_days": c.finding_to_order_days,
        "prior_noshow_count": pat.prior_noshow_count,
        "prior_noshow_ratio": pat.prior_noshow_ratio,
        "days_since_last_encounter": pat.days_since_last_encounter,
        "scheduling_lead_time": c.scheduling_lead_time,
        "distance_miles": pat.distance_miles,
        "insurance_category": pat.insurance,
        "patient_age": pat.age,
        "preferred_language": pat.language,
        "digital_portal_active": 1 if pat.portal_active else 0,
        "stage": c.state if c.state != "CLOSED" else "TREATMENT_OR_SURVEILLANCE",
        "days_in_stage": round(days_in_stage, 2),
        "contact_attempts": c.contact_attempts,
        "acknowledged_flag": 1 if c.acknowledged else 0,
    }


def score_case(
    features: dict[str, Any], model_dir: Path | str | None = None
) -> dict[str, Any]:
    """Score a single case x stage feature dict and return calibrated risk, survival, and SHAP."""
    bundle = get_loaded_models(model_dir)
    x_row = encode_single_case(features).to_numpy()
    p_drop_arr = predict_calibrated(bundle["xgb"], bundle["calibrator"], x_row)
    p_dropoff = round(float(p_drop_arr[0]), 4)

    surv = score_survival_single(bundle["cox"], features)
    shap_drivers = explain_single_case(bundle["explainer"], features, top_k=3)

    return {
        "stage": str(features.get("stage", "RESULT_ISSUED")),
        "p_dropoff": p_dropoff,
        "median_days": surv["median_days"],
        "p_open_30": surv["p_open_30"],
        "p_open_60": surv["p_open_60"],
        "p_open_90": surv["p_open_90"],
        "survival_curve": surv["survival_curve"],
        "km_curve": bundle["km_curve"],
        "shap": shap_drivers,
        "model_version": bundle["model_version"],
    }


def persist_risk_score(
    db: Session,
    *,
    sandbox_id: str,
    case_id: str,
    stage: str,
    scored: dict[str, Any],
    at: datetime,
) -> RiskScore:
    """Create and add a RiskScore ORM row from a `score_case` result dictionary."""
    row = RiskScore(
        sandbox_id=sandbox_id,
        case_id=case_id,
        stage=stage,
        p_dropoff=float(scored["p_dropoff"]),
        median_days=float(scored["median_days"]),
        p_open_30=float(scored["p_open_30"]),
        p_open_60=float(scored["p_open_60"]),
        p_open_90=float(scored["p_open_90"]),
        shap=scored["shap"],
        survival_curve=scored["survival_curve"],
        model_version=str(scored["model_version"]),
        at=at,
    )
    db.add(row)
    return row
