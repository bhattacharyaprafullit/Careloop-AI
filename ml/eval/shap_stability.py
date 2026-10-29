"""SHAP feature ranking stability across 20 bootstrap resamples of the test split (M11)."""
import json
import logging
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from ml.data.generate import DEFAULT_ARTIFACTS_DIR, DEFAULT_OUT_DIR
from ml.data.schema import FEATURE_COLUMNS
from ml.train.explain import build_tree_explainer
from ml.train.features import encode_features, split_by_patient

logger = logging.getLogger(__name__)


def _spearman_rank_corr(a: np.ndarray, b: np.ndarray) -> float:
    """Compute Spearman rank correlation between two 1-D arrays without scipy boilerplate."""
    rank_a = pd.Series(a).rank(method="average").to_numpy(dtype=np.float64)
    rank_b = pd.Series(b).rank(method="average").to_numpy(dtype=np.float64)
    da = rank_a - np.mean(rank_a)
    db = rank_b - np.mean(rank_b)
    denom = float(np.sqrt(np.sum(da * da) * np.sum(db * db)))
    if denom <= 1e-12:
        return 1.0
    return float(np.sum(da * db) / denom)


def evaluate_shap_stability(
    data_dir: Path = DEFAULT_OUT_DIR,
    artifacts_dir: Path = DEFAULT_ARTIFACTS_DIR,
    bootstrap_runs: int = 20,
    sample_size: int = 1000,
    seed: int = 42,
) -> dict[str, Any]:
    """Compute mean Spearman rank correlation and top-3 overlap across 20 bootstrap runs."""
    stage_df = pd.read_parquet(data_dir / "stage_rows.parquet")
    _, _, test_df = split_by_patient(stage_df, seed=42)
    x_test_df = encode_features(test_df, columns=FEATURE_COLUMNS)

    xgb_model = joblib.load(artifacts_dir / "xgb.joblib")
    explainer = build_tree_explainer(xgb_model)

    rng = np.random.default_rng(seed)
    n_rows = len(x_test_df)
    n_draw = min(sample_size, n_rows)

    # Compute full-sample SHAP matrix on a deterministic subset to bootstrap over efficiently
    base_idx = rng.choice(n_rows, size=min(2500, n_rows), replace=False)
    shap_matrix = np.abs(np.asarray(explainer.shap_values(x_test_df.iloc[base_idx])))
    baseline_importance = np.mean(shap_matrix, axis=0)
    baseline_top3 = set(np.argsort(-baseline_importance)[:3].tolist())

    rhos: list[float] = []
    overlaps: list[float] = []
    m = len(base_idx)

    for _ in range(bootstrap_runs):
        boot_idx = rng.choice(m, size=min(n_draw, m), replace=True)
        boot_imp = np.mean(shap_matrix[boot_idx], axis=0)
        rhos.append(_spearman_rank_corr(baseline_importance, boot_imp))
        boot_top3 = set(np.argsort(-boot_imp)[:3].tolist())
        overlaps.append(len(baseline_top3 & boot_top3) / 3.0)

    stability = {
        "bootstrap_runs": bootstrap_runs,
        "mean_spearman_rho": round(float(np.mean(rhos)), 4),
        "min_spearman_rho": round(float(np.min(rhos)), 4),
        "top3_overlap_rate": round(float(np.mean(overlaps)), 4),
    }

    metrics_path = artifacts_dir / "metrics.json"
    if metrics_path.exists():
        payload = json.loads(metrics_path.read_text(encoding="utf-8"))
        if "shap" in payload and isinstance(payload["shap"], dict):
            payload["shap"]["stability"] = stability
        payload["shap_stability"] = stability
        metrics_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
        )

    logger.info("completed SHAP stability evaluation", extra=stability)
    return stability


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    evaluate_shap_stability()
