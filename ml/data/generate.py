"""Synthetic data generator for CareLoop AI (M2).

Uses numpy.random.default_rng(42) with all latent risk and stage coefficients in one dict.
Generates ~12,000 patients/cases, stage_rows, events, and ml/artifacts/seed.json (60 cases).
"""
import argparse
import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Final

import numpy as np
import pandas as pd

from ml.data.schema import (
    CASE_COLUMNS,
    FEATURE_COLUMNS,
    FORBIDDEN_DEMOGRAPHIC_COLUMNS,
    INSURANCE_CATEGORIES,
    LANGUAGE_PROBS,
    LANGUAGES,
    SCREENING_TYPES,
    STAGE_BASE_SLA_HOURS,
    STAGE_ROW_COLUMNS,
    STAGE_SEQUENCE,
)
from ml.data.seed_scenarios import build_seed_cases

logger = logging.getLogger(__name__)

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
DEFAULT_OUT_DIR: Final[Path] = REPO_ROOT / "ml" / "data" / "out"
DEFAULT_ARTIFACTS_DIR: Final[Path] = REPO_ROOT / "ml" / "artifacts"

# All generator parameters and coefficients in one dictionary (spec requirement)
COEFFICIENTS: Final[dict[str, Any]] = {
    "n_patients": 12000,
    "censor_day": 120.0,
    # Latent z = b0 + b1*prior_noshow_ratio + b2*log(1+distance) + b3*(MEDICAID or UNINSURED)
    #            - b4*portal_active + b5*(lead_time>21) + b6*(severity_grade>=4)
    #            + b7*(days_in_stage_ratio) + b8*(contact_attempts>2) - b9*acknowledged + noise
    "b0": -1.95,
    "b1_noshow_ratio": 1.65,
    "b2_log_distance": 0.24,
    "b3_underinsured": 0.48,
    "b4_portal_active": 0.52,
    "b5_long_lead_time": 0.55,
    "b6_high_severity": 0.28,
    "b7_days_in_stage": 0.42,
    "b8_high_contacts": 0.35,
    "b9_acknowledged": 0.30,
    "noise_std": 0.92,
    # Per-stage offset so every stage positive rate is strictly in [0.15, 0.35]
    "stage_offsets": {
        "RESULT_ISSUED": -0.35,
        "PATIENT_NOTIFIED": -0.25,
        "ACKNOWLEDGED": 0.05,
        "CONFIRMATORY_PENDING": 0.18,
        "REFERRAL_SENT": 0.08,
        "REJECTED": 0.24,
        "REFERRAL_ACCEPTED": 0.02,
        "APPOINTMENT_BOOKED": 0.15,
        "SEEN": -0.02,
        "TREATMENT_OR_SURVEILLANCE": 0.06,
    },
    # Stage time lognormal parameters growing with z
    "time_log_scale": 0.32,
    "time_sigma": 0.48,
}


def _sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(x, -30.0, 30.0)))


def _sha256_df(df: pd.DataFrame) -> str:
    raw = pd.util.hash_pandas_object(df, index=True).values.tobytes()
    return hashlib.sha256(raw).hexdigest()


def generate_dataset(
    seed: int = 42,
    n_patients: int = int(COEFFICIENTS["n_patients"]),
    out_dir: Path = DEFAULT_OUT_DIR,
    artifacts_dir: Path = DEFAULT_ARTIFACTS_DIR,
) -> dict[str, Any]:
    """Generate synthetic cases, stage_rows, events, and seed.json deterministically."""
    rng = np.random.default_rng(seed)
    out_dir.mkdir(parents=True, exist_ok=True)
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    # 1. Patient-level features
    ages = (
        np.clip(rng.normal(loc=52.0, scale=14.0, size=n_patients), 25.0, 90.0)
        .round()
        .astype(int)
    )
    langs = rng.choice(LANGUAGES, size=n_patients, p=LANGUAGE_PROBS)

    ins_list: list[str] = []
    for age in ages:
        p_ins = (0.20, 0.65, 0.10, 0.05) if age >= 65 else (0.52, 0.08, 0.25, 0.15)
        ins_list.append(str(rng.choice(INSURANCE_CATEGORIES, p=p_ins)))
    insurances = np.array(ins_list)

    distances = np.clip(
        rng.lognormal(mean=2.1, sigma=0.85, size=n_patients), 0.5, 120.0
    ).round(2)
    portal_prob = np.clip(0.82 - 0.0055 * (ages - 25), 0.20, 0.85)
    portal_active = (rng.random(size=n_patients) < portal_prob).astype(int)

    noshow_ratio = np.clip(rng.beta(a=1.4, b=5.2, size=n_patients), 0.0, 1.0).round(4)
    prior_visits = rng.integers(1, 13, size=n_patients)
    noshow_count = np.clip(np.round(noshow_ratio * prior_visits), 0, 12).astype(int)
    days_since_enc = (
        np.clip(rng.exponential(scale=180.0, size=n_patients), 0.0, 1500.0)
        .round()
        .astype(int)
    )

    # 2. Case-level screening attributes
    screenings = rng.choice(SCREENING_TYPES, size=n_patients, p=(0.40, 0.35, 0.25))
    severity_grade = rng.choice(
        [0, 1, 2, 3, 4, 5], size=n_patients, p=(0.05, 0.18, 0.32, 0.25, 0.13, 0.07)
    )
    urgent_flag = ((severity_grade >= 4) | (rng.random(size=n_patients) < 0.08)).astype(int)
    urgency_tier = np.where(urgent_flag == 1, 1, np.where(severity_grade >= 2, 2, 3))
    finding_to_order = np.clip(
        rng.gamma(shape=2.0, scale=4.5, size=n_patients), 0.0, 60.0
    ).round(1)
    lead_time = np.clip(rng.gamma(shape=2.4, scale=7.5, size=n_patients), 1.0, 90.0).round(1)

    underinsured = np.isin(insurances, ["MEDICAID", "UNINSURED"]).astype(float)
    long_lead = (lead_time > 21.0).astype(float)
    high_sev = (severity_grade >= 4).astype(float)

    base_z = (
        float(COEFFICIENTS["b0"])
        + float(COEFFICIENTS["b1_noshow_ratio"]) * noshow_ratio
        + float(COEFFICIENTS["b2_log_distance"]) * np.log1p(distances)
        + float(COEFFICIENTS["b3_underinsured"]) * underinsured
        - float(COEFFICIENTS["b4_portal_active"]) * portal_active
        + float(COEFFICIENTS["b5_long_lead_time"]) * long_lead
        + float(COEFFICIENTS["b6_high_severity"]) * high_sev
    )

    case_records: list[dict[str, Any]] = []
    stage_records: list[dict[str, Any]] = []
    event_records: list[dict[str, Any]] = []

    stage_offsets: dict[str, float] = COEFFICIENTS["stage_offsets"]
    noise_std = float(COEFFICIENTS["noise_std"])
    time_log_scale = float(COEFFICIENTS["time_log_scale"])
    time_sigma = float(COEFFICIENTS["time_sigma"])
    censor_day = float(COEFFICIENTS["censor_day"])

    for i in range(n_patients):
        cid = f"case-{i + 1:05d}"
        pid = f"pat-{i + 1:05d}"
        u_flag = int(urgent_flag[i])

        needs_confirmatory = bool(rng.random() < 0.45)
        was_rejected = bool(rng.random() < 0.22)

        planned_stages = ["RESULT_ISSUED", "PATIENT_NOTIFIED", "ACKNOWLEDGED"]
        if needs_confirmatory:
            planned_stages.append("CONFIRMATORY_PENDING")
        planned_stages.append("REFERRAL_SENT")
        if was_rejected:
            planned_stages.append("REJECTED")
        planned_stages.extend(
            [
                "REFERRAL_ACCEPTED",
                "APPOINTMENT_BOOKED",
                "SEEN",
                "TREATMENT_OR_SURVEILLANCE",
            ]
        )

        elapsed_hours = 0.0
        final_state = "RESULT_ISSUED"
        closed_flag = 1
        prev_st: str | None = None

        for st in planned_stages:
            base_sla = STAGE_BASE_SLA_HOURS[st]
            sla_h = base_sla / 2.0 if u_flag == 1 else base_sla

            acknowledged_flag = 0 if st in {"RESULT_ISSUED", "PATIENT_NOTIFIED"} else 1
            contact_attempts = int(
                np.clip(
                    rng.poisson(lam=1.2 + (1.5 if base_z[i] > -0.8 else 0.3)),
                    0,
                    8,
                )
            )
            days_in_stage = round(
                float(np.clip(rng.exponential(scale=(sla_h / 24.0) * 0.45), 0.1, 45.0)),
                2,
            )
            days_ratio = min(days_in_stage / max(sla_h / 24.0, 0.5), 2.5)

            z_stage = (
                base_z[i]
                + stage_offsets[st]
                + float(COEFFICIENTS["b7_days_in_stage"]) * (days_ratio - 0.5)
                + float(COEFFICIENTS["b8_high_contacts"]) * float(contact_attempts > 2)
                - float(COEFFICIENTS["b9_acknowledged"]) * float(acknowledged_flag)
                + rng.normal(0.0, noise_std)
            )
            p_drop = float(_sigmoid(np.array([z_stage]))[0])
            dropoff = int(rng.random() < p_drop)

            mean_log_h = np.log(sla_h * 0.52) + time_log_scale * (z_stage + 0.8)
            stage_hours = round(
                float(np.clip(rng.lognormal(mean=mean_log_h, sigma=time_sigma), 1.0, 1440.0)),
                2,
            )

            stage_records.append(
                {
                    "case_id": cid,
                    "patient_id": pid,
                    "screening_type": str(screenings[i]),
                    "severity_grade": int(severity_grade[i]),
                    "urgent_flag": u_flag,
                    "finding_to_order_days": float(finding_to_order[i]),
                    "prior_noshow_count": int(noshow_count[i]),
                    "prior_noshow_ratio": float(noshow_ratio[i]),
                    "days_since_last_encounter": int(days_since_enc[i]),
                    "scheduling_lead_time": float(lead_time[i]),
                    "distance_miles": float(distances[i]),
                    "insurance_category": str(insurances[i]),
                    "patient_age": int(ages[i]),
                    "preferred_language": str(langs[i]),
                    "digital_portal_active": int(portal_active[i]),
                    "stage": st,
                    "days_in_stage": days_in_stage,
                    "contact_attempts": contact_attempts,
                    "acknowledged_flag": acknowledged_flag,
                    "dropoff": dropoff,
                    "stage_hours": stage_hours,
                }
            )

            event_records.append(
                {
                    "case_id": cid,
                    "from_state": prev_st,
                    "to_state": st,
                    "elapsed_hours": round(elapsed_hours, 2),
                    "dropoff": dropoff,
                }
            )
            elapsed_hours += stage_hours
            prev_st = st
            final_state = st

            if dropoff == 1 and rng.random() < 0.35:
                closed_flag = 0
                break

        total_days = elapsed_hours / 24.0
        if total_days > censor_day:
            closed_flag = 0
            days_to_close = censor_day
        elif closed_flag == 1:
            final_state = "CLOSED"
            days_to_close = round(max(1.0, total_days), 2)
        else:
            extra_days = rng.uniform(10.0, 45.0)
            days_to_close = round(min(censor_day, max(1.0, total_days + extra_days)), 2)

        case_records.append(
            {
                "case_id": cid,
                "patient_id": pid,
                "patient_age": int(ages[i]),
                "preferred_language": str(langs[i]),
                "insurance_category": str(insurances[i]),
                "distance_miles": float(distances[i]),
                "digital_portal_active": int(portal_active[i]),
                "prior_noshow_count": int(noshow_count[i]),
                "prior_noshow_ratio": float(noshow_ratio[i]),
                "days_since_last_encounter": int(days_since_enc[i]),
                "screening_type": str(screenings[i]),
                "severity_grade": int(severity_grade[i]),
                "urgent_flag": u_flag,
                "urgency_tier": int(urgency_tier[i]),
                "finding_to_order_days": float(finding_to_order[i]),
                "scheduling_lead_time": float(lead_time[i]),
                "final_state": final_state,
                "closed_flag": int(closed_flag),
                "days_to_close_or_censor": float(days_to_close),
            }
        )

    cases_df = pd.DataFrame(case_records, columns=list(CASE_COLUMNS))
    stage_df = pd.DataFrame(stage_records, columns=list(STAGE_ROW_COLUMNS))
    events_df = pd.DataFrame(event_records)

    assert not (set(stage_df.columns) & FORBIDDEN_DEMOGRAPHIC_COLUMNS)
    meta_cols = {"case_id", "patient_id", "dropoff", "stage_hours"}
    assert list(FEATURE_COLUMNS) == [c for c in stage_df.columns if c not in meta_cols]

    stage_rates: dict[str, float] = {}
    for st in STAGE_SEQUENCE:
        sub = stage_df[stage_df["stage"] == st]
        rate = float(sub["dropoff"].mean())
        stage_rates[st] = round(rate, 4)
        if not (0.15 <= rate <= 0.35):
            raise ValueError(f"Stage {st} positive rate {rate:.4f} outside [0.15, 0.35]")

    cases_path = out_dir / "cases.parquet"
    stage_path = out_dir / "stage_rows.parquet"
    events_path = out_dir / "events.parquet"
    cases_df.to_parquet(cases_path, index=False)
    stage_df.to_parquet(stage_path, index=False)
    events_df.to_parquet(events_path, index=False)

    seed_payload = build_seed_cases()
    seed_path = artifacts_dir / "seed.json"
    seed_path.write_text(json.dumps(seed_payload, indent=2, sort_keys=True), encoding="utf-8")

    hashes = {
        "cases_sha256": _sha256_df(cases_df),
        "stage_rows_sha256": _sha256_df(stage_df),
        "events_sha256": _sha256_df(events_df),
        "seed_json_sha256": hashlib.sha256(seed_path.read_bytes()).hexdigest(),
    }

    summary = {
        "seed": seed,
        "n_patients": int(len(cases_df)),
        "n_stage_rows": int(len(stage_df)),
        "n_events": int(len(events_df)),
        "seed_cases": int(seed_payload["case_count"]),
        "stage_positive_rates": stage_rates,
        "overall_positive_rate": round(float(stage_df["dropoff"].mean()), 4),
        "closed_rate": round(float(cases_df["closed_flag"].mean()), 4),
        "hashes": hashes,
    }
    logger.info("generated synthetic dataset", extra=summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate CareLoop AI synthetic dataset.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--n-patients", type=int, default=int(COEFFICIENTS["n_patients"]))
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    generate_dataset(seed=args.seed, n_patients=args.n_patients)


if __name__ == "__main__":
    main()
