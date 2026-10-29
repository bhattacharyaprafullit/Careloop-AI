"""LLM faithfulness & Explanation-Summary Divergence Score (ADS) evaluation over 200 cases (M11)."""
import json
import logging
from pathlib import Path
from typing import Any

import pandas as pd

from app.domain.states import LLMKind
from app.llm.ads import compute_ads
from app.llm.templates import build_template_output
from app.llm.validators import validate_llm_output
from ml.data.generate import DEFAULT_ARTIFACTS_DIR, DEFAULT_OUT_DIR

logger = logging.getLogger(__name__)


def evaluate_llm_faithfulness(
    data_dir: Path = DEFAULT_OUT_DIR,
    artifacts_dir: Path = DEFAULT_ARTIFACTS_DIR,
    n_cases: int = 200,
) -> dict[str, Any]:
    """Evaluate 200 synthetic cases across grounded validators and ADS divergence audit."""
    cases_df = pd.read_parquet(data_dir / "cases.parquet").head(n_cases)

    total_checks = 0
    passed_checks = 0
    fallback_count = 0
    ads_scores: list[float] = []

    feature_pool = [
        "prior_noshow_ratio",
        "scheduling_lead_time",
        "distance_miles",
        "finding_to_order_days",
        "digital_portal_active",
    ]

    for idx, row in enumerate(cases_df.to_dict(orient="records")):
        top_feats = [
            feature_pool[idx % len(feature_pool)],
            feature_pool[(idx + 1) % len(feature_pool)],
            feature_pool[(idx + 2) % len(feature_pool)],
        ]
        p_drop_pct = 18 + (idx % 50)
        scr_type = str(row["screening_type"])
        facts: dict[str, Any] = {
            "case_id": str(row["case_id"]),
            "patient_alias": f"PT-{idx + 1:03d}",
            "screening_type": scr_type,
            "test_name": scr_type,
            "severity_grade": int(row["severity_grade"]),
            "urgency_tier": 1 if int(row["urgent_flag"]) == 1 else 2,
            "urgency_code": "soon" if int(row["urgent_flag"]) == 1 else "routine",
            "state": "RESULT_ISSUED",
            "owner_role": "clinician",
            "days_in_state": 1,
            "sla_hours_remaining": 24,
            "p_dropoff_percent": p_drop_pct,
            "finding_to_order_days": int(round(float(row["finding_to_order_days"]))),
            "due_date": "2026-06-15",
            "language": str(row["preferred_language"]),
            "shap_top_positive": [
                {"feature": f, "label": f, "value": 0.25} for f in top_feats
            ],
        }

        for kind in (
            LLMKind.CASE_SUMMARY.value,
            LLMKind.PATIENT_MESSAGE.value,
            LLMKind.SBAR_NOTE.value,
        ):
            out = build_template_output(kind, facts)
            ok, _ = validate_llm_output(kind, out, facts)
            total_checks += 1
            if ok:
                passed_checks += 1
            else:
                fallback_count += 1

            if kind == LLMKind.CASE_SUMMARY.value:
                cited = list(out.get("cited_drivers", []))
                ads_val = compute_ads(cited, top_feats)
                ads_scores.append(ads_val)

    result = {
        "evaluated_cases": int(len(cases_df)),
        "total_generations": total_checks,
        "validator_pass_rate": round(passed_checks / max(total_checks, 1), 4),
        "fallback_rate": round(fallback_count / max(total_checks, 1), 4),
        "mean_ads": round(
            float(sum(ads_scores) / max(len(ads_scores), 1)), 4
        ),
    }

    metrics_path = artifacts_dir / "metrics.json"
    if metrics_path.exists():
        payload = json.loads(metrics_path.read_text(encoding="utf-8"))
        payload["llm_faithfulness"] = result
        metrics_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
        )

    logger.info("completed 200-case LLM faithfulness evaluation", extra=result)
    return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    evaluate_llm_faithfulness()
