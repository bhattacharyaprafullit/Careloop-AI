"""Subgroup fairness evaluation across age, insurance, language, distance, and screening (M11)."""
import json
import logging
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from ml.data.generate import DEFAULT_ARTIFACTS_DIR, DEFAULT_OUT_DIR
from ml.data.schema import FEATURE_COLUMNS
from ml.train.calibrate import predict_calibrated
from ml.train.features import add_evaluation_slices, encode_features, split_by_patient

logger = logging.getLogger(__name__)


def evaluate_subgroup_fairness(
    data_dir: Path = DEFAULT_OUT_DIR,
    artifacts_dir: Path = DEFAULT_ARTIFACTS_DIR,
    threshold: float = 0.35,
) -> dict[str, Any]:
    """Compute FPR, FNR, and positive rates across demographic and clinical slices on test split."""
    stage_df = pd.read_parquet(data_dir / "stage_rows.parquet")
    _, _, test_df = split_by_patient(stage_df, seed=42)

    xgb_model = joblib.load(artifacts_dir / "xgb.joblib")
    calibrator = joblib.load(artifacts_dir / "calibrator.joblib")

    x_test = encode_features(test_df, columns=FEATURE_COLUMNS).to_numpy()
    y_test = test_df["dropoff"].astype(int).to_numpy()
    y_prob = predict_calibrated(xgb_model, calibrator, x_test)
    y_pred = (y_prob >= threshold).astype(int)

    sliced = add_evaluation_slices(test_df)
    slice_cols = (
        "age_bracket",
        "insurance_category",
        "preferred_language",
        "distance_band",
        "screening_type",
    )

    dimensions: dict[str, Any] = {}
    largest_fpr_gap = 0.0
    largest_fnr_gap = 0.0
    largest_gap_dim = ""

    for col in slice_cols:
        slices: dict[str, dict[str, float | int]] = {}
        fprs: list[float] = []
        fnrs: list[float] = []
        for val, grp in sliced.groupby(col):
            idx = grp.index.to_numpy()
            yt = y_test[idx]
            yp = y_pred[idx]
            pos = int(np.sum(yt == 1))
            neg = int(np.sum(yt == 0))
            fp = int(np.sum((yp == 1) & (yt == 0)))
            fn = int(np.sum((yp == 0) & (yt == 1)))
            fpr = round(fp / neg, 4) if neg > 0 else 0.0
            fnr = round(fn / pos, 4) if pos > 0 else 0.0
            fprs.append(fpr)
            fnrs.append(fnr)
            slices[str(val)] = {
                "n": int(len(idx)),
                "positive_rate": round(float(np.mean(yt)), 4),
                "fpr": fpr,
                "fnr": fnr,
            }
        fpr_gap = round(max(fprs) - min(fprs), 4) if fprs else 0.0
        fnr_gap = round(max(fnrs) - min(fnrs), 4) if fnrs else 0.0
        if max(fpr_gap, fnr_gap) > max(largest_fpr_gap, largest_fnr_gap):
            largest_gap_dim = col
        largest_fpr_gap = max(largest_fpr_gap, fpr_gap)
        largest_fnr_gap = max(largest_fnr_gap, fnr_gap)
        dimensions[col] = {
            "fpr_gap": fpr_gap,
            "fnr_gap": fnr_gap,
            "slices": slices,
        }

    result = {
        "threshold": threshold,
        "largest_fpr_gap": round(largest_fpr_gap, 4),
        "largest_fnr_gap": round(largest_fnr_gap, 4),
        "largest_gap_dimension": largest_gap_dim,
        "dimensions": dimensions,
    }

    metrics_path = artifacts_dir / "metrics.json"
    if metrics_path.exists():
        payload = json.loads(metrics_path.read_text(encoding="utf-8"))
        payload["fairness"] = result
        metrics_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
        )

    logger.info(
        "completed subgroup fairness evaluation",
        extra={
            "largest_fpr_gap": result["largest_fpr_gap"],
            "largest_fnr_gap": result["largest_fnr_gap"],
        },
    )
    return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    evaluate_subgroup_fairness()
