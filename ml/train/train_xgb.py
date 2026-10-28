"""Train XGBClassifier for stage drop-off / SLA-miss prediction (M3)."""
import logging
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
from xgboost import XGBClassifier

from ml.data.schema import FEATURE_COLUMNS
from ml.train.features import encode_features

logger = logging.getLogger(__name__)


def train_xgb_model(
    train_df: pd.DataFrame,
    cal_df: pd.DataFrame,
    artifacts_dir: Path | None = None,
) -> tuple[XGBClassifier, dict[str, Any]]:
    """Fit XGBClassifier with exact spec hyperparameters and early stopping on calibration set."""
    x_train = encode_features(train_df, columns=FEATURE_COLUMNS)
    y_train = train_df["dropoff"].astype(int).to_numpy()

    x_cal = encode_features(cal_df, columns=FEATURE_COLUMNS)
    y_cal = cal_df["dropoff"].astype(int).to_numpy()

    model = XGBClassifier(
        max_depth=4,
        n_estimators=400,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        early_stopping_rounds=30,
        eval_metric="aucpr",
        random_state=42,
    )
    model.fit(
        x_train,
        y_train,
        eval_set=[(x_cal, y_cal)],
        verbose=False,
    )

    if artifacts_dir is not None:
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        joblib.dump(model, artifacts_dir / "xgb.joblib")

    info = {
        "best_iteration": int(getattr(model, "best_iteration", model.n_estimators)),
        "feature_names": list(FEATURE_COLUMNS),
    }
    logger.info("trained XGBClassifier", extra=info)
    return model, info
