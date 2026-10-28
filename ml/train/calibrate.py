"""Isotonic calibration and Expected Calibration Error (ECE) computation (M3)."""
import logging
from pathlib import Path

import joblib
import numpy as np
from sklearn.isotonic import IsotonicRegression
from xgboost import XGBClassifier

logger = logging.getLogger(__name__)


def compute_ece(y_true: np.ndarray, y_prob: np.ndarray, n_bins: int = 10) -> float:
    """Compute Expected Calibration Error across `n_bins` uniform probability bins."""
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    binids = np.digitize(y_prob, bins[1:-1], right=True)
    ece = 0.0
    n = float(len(y_true))
    for b in range(n_bins):
        mask = binids == b
        if np.any(mask):
            acc = float(np.mean(y_true[mask]))
            conf = float(np.mean(y_prob[mask]))
            ece += (np.sum(mask) / n) * abs(acc - conf)
    return float(ece)


def reliability_curve_bins(
    y_true: np.ndarray, y_prob: np.ndarray, n_bins: int = 10
) -> list[dict[str, float | int]]:
    """Return bin-level mean predicted probability and empirical fraction of positives."""
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    binids = np.digitize(y_prob, bins[1:-1], right=True)
    rows: list[dict[str, float | int]] = []
    for b in range(n_bins):
        mask = binids == b
        count = int(np.sum(mask))
        if count > 0:
            rows.append(
                {
                    "bin": b,
                    "count": count,
                    "mean_pred": round(float(np.mean(y_prob[mask])), 4),
                    "frac_pos": round(float(np.mean(y_true[mask])), 4),
                }
            )
    return rows


def fit_isotonic_calibrator(
    model: XGBClassifier,
    x_cal: np.ndarray,
    y_cal: np.ndarray,
    artifacts_dir: Path | None = None,
) -> IsotonicRegression:
    """Fit IsotonicRegression on raw XGBClassifier probabilities from calibration split."""
    raw_probs = model.predict_proba(x_cal)[:, 1]
    iso = IsotonicRegression(y_min=0.001, y_max=0.999, out_of_bounds="clip")
    iso.fit(raw_probs, y_cal)
    if artifacts_dir is not None:
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        joblib.dump(iso, artifacts_dir / "calibrator.joblib")
    logger.info("fitted isotonic calibrator")
    return iso


def predict_calibrated(
    model: XGBClassifier, calibrator: IsotonicRegression, x: np.ndarray
) -> np.ndarray:
    """Return isotonic-calibrated drop-off probabilities."""
    raw = model.predict_proba(x)[:, 1]
    return np.asarray(calibrator.predict(raw), dtype=float)
