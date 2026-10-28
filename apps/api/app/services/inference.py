"""ML inference service: load_models(model_dir) once at startup and score_case(features)."""
import json
import logging
from pathlib import Path
from typing import Any

import joblib
from ml.train.calibrate import predict_calibrated
from ml.train.explain import build_tree_explainer, explain_single_case
from ml.train.features import encode_single_case
from ml.train.train_cox import score_survival_single

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
