"""Survival modeling on days to CLOSED, censored at day 120 (M3).

Fits lifelines CoxPHFitter(penalizer=0.1), runs check_assumptions, and falls back to
WeibullAFTFitter if proportional-hazards assumptions are violated.
Hazard here means completion rate (higher = faster closure).
"""
import logging
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from lifelines import CoxPHFitter, KaplanMeierFitter, WeibullAFTFitter
from lifelines.statistics import proportional_hazard_test

from ml.train.features import COX_FEATURE_COLUMNS, encode_features

logger = logging.getLogger(__name__)

SURVIVAL_DAYS: tuple[int, ...] = (0, 15, 30, 45, 60, 75, 90, 105, 120)


def prepare_survival_df(cases_df: pd.DataFrame) -> pd.DataFrame:
    """Prepare encoded covariates + duration + event columns for lifelines."""
    x = encode_features(cases_df, columns=COX_FEATURE_COLUMNS)
    x["duration"] = np.clip(
        pd.to_numeric(cases_df["days_to_close_or_censor"], errors="coerce").fillna(30.0),
        0.5,
        120.0,
    )
    x["event"] = cases_df["closed_flag"].astype(int)
    return x


def train_survival_model(
    cases_df: pd.DataFrame,
    artifacts_dir: Path | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Fit CoxPHFitter(penalizer=0.1), check assumptions, fall back to WeibullAFT if violated."""
    surv_df = prepare_survival_df(cases_df)
    cph = CoxPHFitter(penalizer=0.1)
    cph.fit(surv_df, duration_col="duration", event_col="event")

    ph_violated = False
    violated_vars: list[str] = []
    try:
        cph.check_assumptions(surv_df, p_value_threshold=0.01, show_plots=False, advice=False)
        ph_test = proportional_hazard_test(cph, surv_df, time_transform="rank")
        p_series = ph_test.summary["p"]
        violated_vars = [str(idx) for idx, pval in p_series.items() if float(pval) < 0.01]
        if violated_vars:
            ph_violated = True
    except Exception as exc:
        logger.info("cox check_assumptions flagged; using fallback", extra={"err": str(exc)})
        ph_violated = True

    if ph_violated:
        aft = WeibullAFTFitter(penalizer=0.1)
        aft.fit(surv_df, duration_col="duration", event_col="event")
        fitted_model: Any = aft
        model_type = "WeibullAFTFitter"
        c_index = float(aft.concordance_index_)
    else:
        fitted_model = cph
        model_type = "CoxPHFitter"
        c_index = float(cph.concordance_index_)

    kmf = KaplanMeierFitter()
    kmf.fit(surv_df["duration"], event_observed=surv_df["event"])
    km_curve: list[dict[str, float | int]] = []
    for d in SURVIVAL_DAYS:
        s_val = float(kmf.predict(d))
        km_curve.append({"day": int(d), "s": round(max(0.0, min(1.0, s_val)), 4)})

    bundle = {
        "model": fitted_model,
        "model_type": model_type,
        "ph_violated": ph_violated,
        "violated_covariates": violated_vars,
        "concordance_index": round(c_index, 4),
        "feature_columns": list(COX_FEATURE_COLUMNS),
        "km_curve": km_curve,
        "meaning": "completion_rate_higher_means_faster_closure",
    }
    if artifacts_dir is not None:
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        joblib.dump(bundle, artifacts_dir / "cox.joblib")

    info = {
        "model_type": model_type,
        "ph_violated": ph_violated,
        "violated_covariates": violated_vars,
        "concordance_index": round(c_index, 4),
        "km_curve": km_curve,
    }
    logger.info("trained survival model", extra=info)
    return bundle, info


def score_survival_single(bundle: dict[str, Any], features: dict[str, Any]) -> dict[str, Any]:
    """Compute survival curve S(t) = P(still open at day t), p_open_30/60/90, and median_days."""
    row = {col: features.get(col, 0) for col in COX_FEATURE_COLUMNS}
    x_row = encode_features(pd.DataFrame([row]), columns=COX_FEATURE_COLUMNS)
    model = bundle["model"]

    sf = model.predict_survival_function(x_row, times=list(SURVIVAL_DAYS))
    curve: list[dict[str, float | int]] = []
    by_day: dict[int, float] = {}
    for d in SURVIVAL_DAYS:
        val = float(sf.loc[d].iloc[0]) if d in sf.index else float(sf.iloc[-1].iloc[0])
        s_clean = round(max(0.0, min(1.0, val)), 4)
        by_day[int(d)] = s_clean
        curve.append({"day": int(d), "s": s_clean})

    med_raw = model.predict_median(x_row)
    med_val = float(np.asarray(med_raw).ravel()[0])
    if not np.isfinite(med_val) or med_val > 120.0:
        med_val = 120.0
    median_days = round(max(1.0, med_val), 1)

    return {
        "median_days": median_days,
        "p_open_30": by_day[30],
        "p_open_60": by_day[60],
        "p_open_90": by_day[90],
        "survival_curve": curve,
    }
