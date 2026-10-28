"""M3 ML unit tests: thresholds, calibration, SHAP log-odds, subprocess artifact loading."""
import json
import logging
import subprocess
import sys
from pathlib import Path

import pytest
from ml.data.generate import DEFAULT_ARTIFACTS_DIR

from app.services.inference import ModelArtifactsMissingError, load_models, score_case

logger = logging.getLogger(__name__)


def test_ml_metrics_meet_diagnostic_thresholds() -> None:
    metrics_path = DEFAULT_ARTIFACTS_DIR / "metrics.json"
    assert metrics_path.exists(), "ml/artifacts/metrics.json must exist"
    m = json.loads(metrics_path.read_text(encoding="utf-8"))

    roc_auc = float(m["classification"]["roc_auc"])
    ece = float(m["classification"]["ece_calibrated"])
    brier = float(m["classification"]["brier_calibrated"])
    total_mb = float(m["artifacts_total_mb"])

    # ROC-AUC is reported honestly on the unmanipulated M2 generator (no leakage <= 0.90)
    assert 0.60 <= roc_auc <= 0.90, f"ROC-AUC {roc_auc} unexpected"
    assert "roc_auc_diagnostic_target" in m["classification"]
    assert ece <= 0.05, f"Calibrated ECE {ece} > 0.05"
    assert 0.0 < brier < 0.30
    assert total_mb < 25.0

    # Survival fallback check: Cox PH violation on large cohort triggers WeibullAFTFitter fallback
    assert m["survival"]["model_type"] in {"CoxPHFitter", "WeibullAFTFitter"}
    if m["survival"]["ph_violated"]:
        assert m["survival"]["model_type"] == "WeibullAFTFitter"

    # Check per-slice fairness dimensions
    dims = m["fairness"]["dimensions"]
    for req_dim in ("age_bracket", "insurance_category", "preferred_language", "distance_band"):
        assert req_dim in dims
        assert len(dims[req_dim]["slices"]) >= 2
    assert m["fairness"]["largest_gap_dimension"] in dims
    assert m["shap"]["units"] == "log-odds"
    assert "not evidence of real-world" in m["synthetic_disclaimer"].lower()


def test_artifacts_load_and_score_in_fresh_process() -> None:
    code = (
        "from app.services.inference import load_models, score_case; "
        "from ml.data.generate import DEFAULT_ARTIFACTS_DIR; "
        "load_models(DEFAULT_ARTIFACTS_DIR); "
        "res = score_case({'screening_type': 'FIT', 'severity_grade': 3, 'urgent_flag': 1, "
        "'finding_to_order_days': 7, 'prior_noshow_count': 2, 'prior_noshow_ratio': 0.4, "
        "'days_since_last_encounter': 90, 'scheduling_lead_time': 25, 'distance_miles': 18.5, "
        "'insurance_category': 'MEDICAID', 'patient_age': 58, 'preferred_language': 'es', "
        "'digital_portal_active': 0, 'stage': 'PATIENT_NOTIFIED', 'days_in_stage': 2.0, "
        "'contact_attempts': 2, 'acknowledged_flag': 0}, DEFAULT_ARTIFACTS_DIR); "
        "assert 0.0 < res['p_dropoff'] < 1.0; "
        "assert len(res['shap']['top_positive']) >= 1; "
        "assert 'log-odds' in res['shap']['top_positive'][0]['label']"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, f"Subprocess failed: {proc.stderr}"


def test_load_models_raises_clear_error_when_missing(tmp_path: Path) -> None:
    with pytest.raises(ModelArtifactsMissingError, match="Missing trained ML artifacts"):
        load_models(tmp_path)


def test_score_case_returns_expected_contract() -> None:
    load_models(DEFAULT_ARTIFACTS_DIR)
    out = score_case(
        {
            "screening_type": "MAMMOGRAPHY",
            "severity_grade": 4,
            "urgent_flag": 1,
            "finding_to_order_days": 5,
            "prior_noshow_count": 3,
            "prior_noshow_ratio": 0.5,
            "days_since_last_encounter": 200,
            "scheduling_lead_time": 30,
            "distance_miles": 22.0,
            "insurance_category": "UNINSURED",
            "patient_age": 62,
            "preferred_language": "hi",
            "digital_portal_active": 0,
            "stage": "REFERRAL_SENT",
            "days_in_stage": 1.5,
            "contact_attempts": 3,
            "acknowledged_flag": 1,
        },
        DEFAULT_ARTIFACTS_DIR,
    )
    assert set(out.keys()) >= {
        "p_dropoff",
        "median_days",
        "p_open_30",
        "p_open_60",
        "p_open_90",
        "survival_curve",
        "shap",
        "model_version",
    }
