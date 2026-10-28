"""Feature encoding, human-readable labels, and GroupShuffleSplit (60/15/25 by patient_id)."""
import logging
from typing import Any, Final

import pandas as pd
from sklearn.model_selection import GroupShuffleSplit

from ml.data.schema import (
    FEATURE_COLUMNS,
    FORBIDDEN_DEMOGRAPHIC_COLUMNS,
    INSURANCE_CATEGORIES,
    LANGUAGES,
    SCREENING_TYPES,
    STAGE_SEQUENCE,
)

logger = logging.getLogger(__name__)

CATEGORICAL_MAPS: Final[dict[str, dict[str, int]]] = {
    "screening_type": {v: i for i, v in enumerate(SCREENING_TYPES)},
    "insurance_category": {v: i for i, v in enumerate(INSURANCE_CATEGORIES)},
    "preferred_language": {v: i for i, v in enumerate(LANGUAGES)},
    "stage": {v: i for i, v in enumerate(STAGE_SEQUENCE)},
}

FEATURE_LABELS: Final[dict[str, str]] = {
    "screening_type": "Screening modality (FIT / Mammography / Pap-HPV)",
    "severity_grade": "Abnormality severity grade (0-5 scale)",
    "urgent_flag": "Urgent clinical tier flag (0/1)",
    "finding_to_order_days": "Days from abnormal finding to order (days)",
    "prior_noshow_count": "Prior missed appointment count (visits)",
    "prior_noshow_ratio": "Historical appointment no-show ratio (0-1)",
    "days_since_last_encounter": "Time since last clinical encounter (days)",
    "scheduling_lead_time": "Appointment scheduling lead time (days)",
    "distance_miles": "Patient distance to facility (miles)",
    "insurance_category": "Insurance coverage category",
    "patient_age": "Patient age (years)",
    "preferred_language": "Preferred communication language",
    "digital_portal_active": "Active patient portal account (0/1)",
    "stage": "Current care-loop workflow stage",
    "days_in_stage": "Elapsed time in current stage (days)",
    "contact_attempts": "Coordinator outreach attempts (count)",
    "acknowledged_flag": "Patient result acknowledgement recorded (0/1)",
}

COX_FEATURE_COLUMNS: Final[tuple[str, ...]] = (
    "screening_type",
    "severity_grade",
    "urgent_flag",
    "finding_to_order_days",
    "prior_noshow_count",
    "prior_noshow_ratio",
    "days_since_last_encounter",
    "scheduling_lead_time",
    "distance_miles",
    "insurance_category",
    "patient_age",
    "preferred_language",
    "digital_portal_active",
)


def encode_features(df: pd.DataFrame, columns: tuple[str, ...] = FEATURE_COLUMNS) -> pd.DataFrame:
    """Convert raw feature dataframe into a numeric matrix with exact column names."""
    bad = set(df.columns) & FORBIDDEN_DEMOGRAPHIC_COLUMNS
    if bad:
        raise ValueError(f"Forbidden demographic columns present: {sorted(bad)}")
    out = pd.DataFrame(index=df.index)
    for col in columns:
        if col in CATEGORICAL_MAPS:
            cmap = CATEGORICAL_MAPS[col]
            out[col] = df[col].map(lambda x, m=cmap: m.get(str(x), 0)).astype(float)
        else:
            out[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0).astype(float)
    return out


def encode_single_case(features: dict[str, Any]) -> pd.DataFrame:
    """Encode a single feature dictionary into a 1-row DataFrame matching FEATURE_COLUMNS."""
    row = {col: features.get(col, 0) for col in FEATURE_COLUMNS}
    return encode_features(pd.DataFrame([row]), columns=FEATURE_COLUMNS)


def split_by_patient(
    df: pd.DataFrame, seed: int = 42
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Split stage rows into 60% train, 15% calibration, 25% test grouped by patient_id."""
    gss_outer = GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=seed)
    train_cal_idx, test_idx = next(gss_outer.split(df, groups=df["patient_id"]))
    train_cal_df = df.iloc[train_cal_idx].reset_index(drop=True)
    test_df = df.iloc[test_idx].reset_index(drop=True)

    # 15 / 75 = 0.20 of train_cal
    gss_inner = GroupShuffleSplit(n_splits=1, test_size=0.20, random_state=seed + 1)
    train_idx, cal_idx = next(gss_inner.split(train_cal_df, groups=train_cal_df["patient_id"]))
    train_df = train_cal_df.iloc[train_idx].reset_index(drop=True)
    cal_df = train_cal_df.iloc[cal_idx].reset_index(drop=True)

    # Verify zero patient overlap across splits
    p_train = set(train_df["patient_id"])
    p_cal = set(cal_df["patient_id"])
    p_test = set(test_df["patient_id"])
    assert not (p_train & p_cal)
    assert not (p_train & p_test)
    assert not (p_cal & p_test)
    return train_df, cal_df, test_df


def add_evaluation_slices(df: pd.DataFrame) -> pd.DataFrame:
    """Add age_bracket, distance_band, insurance_category, preferred_language slice columns."""
    out = df.copy()
    out["age_bracket"] = pd.cut(
        out["patient_age"],
        bins=[0, 40, 60, 75, 120],
        labels=["25-40", "41-60", "61-75", "76+"],
    ).astype(str)
    out["distance_band"] = pd.cut(
        out["distance_miles"],
        bins=[-1, 5, 15, 35, 200],
        labels=["0-5mi", "5-15mi", "15-35mi", "35mi+"],
    ).astype(str)
    return out
