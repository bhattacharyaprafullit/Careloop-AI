"""SHAP TreeExplainer in log-odds units with human-readable feature labels (M3)."""
import logging
from typing import Any

import numpy as np
import pandas as pd
import shap
from xgboost import XGBClassifier

from ml.data.schema import FEATURE_COLUMNS
from ml.train.features import FEATURE_LABELS, encode_single_case

logger = logging.getLogger(__name__)


def build_tree_explainer(model: XGBClassifier) -> shap.TreeExplainer:
    """Create a SHAP TreeExplainer reporting in log-odds (raw margin), never percentages."""
    return shap.TreeExplainer(model, model_output="raw")


def explain_single_case(
    explainer: shap.TreeExplainer,
    features: dict[str, Any],
    top_k: int = 3,
) -> dict[str, list[dict[str, Any]]]:
    """Return top_positive and top_negative SHAP drivers in log-odds units."""
    x_row = encode_single_case(features)
    shap_vals = explainer.shap_values(x_row)
    arr = np.asarray(shap_vals, dtype=float).ravel()

    items: list[dict[str, Any]] = []
    for feat_name, val in zip(FEATURE_COLUMNS, arr, strict=True):
        items.append(
            {
                "feature": feat_name,
                "label": f"{FEATURE_LABELS.get(feat_name, feat_name)} (log-odds)",
                "value": round(float(val), 4),
            }
        )

    pos = sorted([it for it in items if it["value"] > 0], key=lambda d: -d["value"])[:top_k]
    neg = sorted([it for it in items if it["value"] < 0], key=lambda d: d["value"])[:top_k]

    # Guarantee up to top_k entries even if all values have the same sign
    if not pos:
        pos = sorted(items, key=lambda d: -d["value"])[:1]
    if not neg:
        neg = sorted(items, key=lambda d: d["value"])[:1]

    return {"top_positive": pos, "top_negative": neg}


def global_feature_importance(
    explainer: shap.TreeExplainer, x_df: pd.DataFrame
) -> list[dict[str, Any]]:
    """Compute mean absolute SHAP (log-odds) across a sample of rows."""
    sample = x_df.iloc[: min(1000, len(x_df))]
    sv = np.asarray(explainer.shap_values(sample), dtype=float)
    mean_abs = np.mean(np.abs(sv), axis=0)
    ranked = sorted(
        zip(FEATURE_COLUMNS, mean_abs, strict=True), key=lambda pair: -float(pair[1])
    )
    return [
        {
            "feature": name,
            "label": FEATURE_LABELS.get(name, name),
            "mean_abs_log_odds": round(float(val), 4),
            "units": "log-odds",
        }
        for name, val in ranked
    ]
