"""Pure domain metric calculations from case, event, message, and closure records."""
import logging
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

import numpy as np

from app.core.clock import ClockFn, utc_now
from app.domain.states import ALL_STATES, CaseState, TeachBackLabel

logger = logging.getLogger(__name__)

INTERVAL_PAIRS: dict[str, tuple[str, set[str]]] = {
    "result_to_notified": (CaseState.RESULT_ISSUED.value, {CaseState.PATIENT_NOTIFIED.value}),
    "notified_to_ack": (CaseState.PATIENT_NOTIFIED.value, {CaseState.ACKNOWLEDGED.value}),
    "ack_to_confirmatory": (
        CaseState.ACKNOWLEDGED.value,
        {CaseState.CONFIRMATORY_PENDING.value, CaseState.REFERRAL_SENT.value},
    ),
    "referral_to_accept": (CaseState.REFERRAL_SENT.value, {CaseState.REFERRAL_ACCEPTED.value}),
    "accept_to_appointment": (
        CaseState.REFERRAL_ACCEPTED.value,
        {CaseState.APPOINTMENT_BOOKED.value},
    ),
    "appointment_to_seen": (CaseState.APPOINTMENT_BOOKED.value, {CaseState.SEEN.value}),
    "seen_to_plan": (CaseState.SEEN.value, {CaseState.TREATMENT_OR_SURVEILLANCE.value}),
    "result_to_closed": (CaseState.RESULT_ISSUED.value, {CaseState.CLOSED.value}),
}


def _to_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


def _summarize_hours(samples: list[float]) -> dict[str, float | int | None]:
    if not samples:
        return {"median_hours": None, "p90_hours": None, "n": 0}
    arr = np.asarray(samples, dtype=float)
    return {
        "median_hours": round(float(np.median(arr)), 2),
        "p90_hours": round(float(np.percentile(arr, 90)), 2),
        "n": int(arr.size),
    }


def compute_intervals_from_events(
    events: Sequence[dict[str, Any]],
) -> dict[str, dict[str, float | int | None]]:
    """Compute median_hours, p90_hours, and n for each transition interval from case_events."""
    by_case: dict[str, list[dict[str, Any]]] = {}
    for ev in events:
        cid = str(ev["case_id"])
        by_case.setdefault(cid, []).append(ev)

    state_times: dict[str, dict[str, datetime]] = {}
    for cid, ev_list in by_case.items():
        ordered = sorted(ev_list, key=lambda x: _to_utc(x["at"]))
        times: dict[str, datetime] = {}
        for ev in ordered:
            to_st = ev.get("to_state")
            if to_st and to_st not in times:
                times[to_st] = _to_utc(ev["at"])
        state_times[cid] = times

    result: dict[str, dict[str, float | int | None]] = {}
    for name, (start_state, end_states) in INTERVAL_PAIRS.items():
        samples: list[float] = []
        for times in state_times.values():
            t0 = times.get(start_state)
            if t0 is None:
                continue
            t1_candidates = [times[s] for s in end_states if s in times and times[s] >= t0]
            if t1_candidates:
                t1 = min(t1_candidates)
                samples.append((t1 - t0).total_seconds() / 3600.0)
        result[name] = _summarize_hours(samples)
    return result


def compute_metrics_summary(
    *,
    cases: Sequence[dict[str, Any]],
    events: Sequence[dict[str, Any]],
    referrals: Sequence[dict[str, Any]],
    closures: Sequence[dict[str, Any]],
    delay_reasons: Sequence[dict[str, Any]],
    messages: Sequence[dict[str, Any]],
    simulation: dict[str, Any],
    clock: ClockFn = utc_now,
) -> dict[str, Any]:
    """Compute the full R6 metrics summary from domain records and events."""
    now = _to_utc(clock())
    state_counts = {s.value: 0 for s in ALL_STATES}
    for c in cases:
        st = str(c["state"])
        state_counts[st] = state_counts.get(st, 0) + 1

    intervals = compute_intervals_from_events(events)

    total_refs = len(referrals)
    accepted_refs = sum(1 for r in referrals if r.get("status") == "accepted")
    referral_completion_rate = round(accepted_refs / total_refs, 4) if total_refs else 0.0

    # Appointment completion: cases reaching SEEN or later among APPOINTMENT_BOOKED cases
    cases_booked: set[str] = set()
    cases_seen: set[str] = set()
    for ev in events:
        if ev.get("to_state") == CaseState.APPOINTMENT_BOOKED.value:
            cases_booked.add(str(ev["case_id"]))
        if ev.get("to_state") in {
            CaseState.SEEN.value,
            CaseState.TREATMENT_OR_SURVEILLANCE.value,
            CaseState.CLOSED.value,
        }:
            cases_seen.add(str(ev["case_id"]))
    booked_n = len(cases_booked)
    appointment_completion_rate = (
        round(len(cases_booked & cases_seen) / booked_n, 4) if booked_n else 0.0
    )

    aging = {"d0_30": 0, "d31_60": 0, "d61_90": 0, "d90_plus": 0}
    unresolved_total = 0
    for c in cases:
        if c["state"] != CaseState.CLOSED.value:
            unresolved_total += 1
            created = _to_utc(c["created_at"])
            age_days = max(0.0, (now - created).total_seconds() / 86400.0)
            if age_days <= 30:
                aging["d0_30"] += 1
            elif age_days <= 60:
                aging["d31_60"] += 1
            elif age_days <= 90:
                aging["d61_90"] += 1
            else:
                aging["d90_plus"] += 1

    reason_counts: dict[str, int] = {}
    for dr in delay_reasons:
        code = str(dr["code"])
        reason_counts[code] = reason_counts.get(code, 0) + 1
    delay_list = [
        {"code": k, "count": v}
        for k, v in sorted(reason_counts.items(), key=lambda x: (-x[1], x[0]))
    ]

    closed_cases = [c for c in cases if c["state"] == CaseState.CLOSED.value]
    evidence_closures = sum(1 for cl in closures if cl.get("kind") == "evidence")
    documented_closure_rate = (
        round(evidence_closures / len(closed_cases), 4) if closed_cases else 0.0
    )

    notified_cases = [c for c in cases if c["state"] != CaseState.RESULT_ISSUED.value]
    acked_cases = sum(1 for c in notified_cases if c.get("acknowledged"))
    acknowledgement_rate = (
        round(acked_cases / len(notified_cases), 4) if notified_cases else 0.0
    )

    tb_counts = {
        TeachBackLabel.UNDERSTOOD.value: 0,
        TeachBackLabel.PARTIAL.value: 0,
        TeachBackLabel.CONFUSED.value: 0,
    }
    for m in messages:
        lbl = m.get("teachback_label")
        if lbl in tb_counts:
            tb_counts[lbl] += 1

    return {
        "state_counts": state_counts,
        "intervals": intervals,
        "referral_completion_rate": referral_completion_rate,
        "appointment_completion_rate": appointment_completion_rate,
        "unresolved": {"total": unresolved_total, "aging": aging},
        "delay_reasons": delay_list,
        "documented_closure_rate": documented_closure_rate,
        "acknowledgement_rate": acknowledgement_rate,
        "teachback": tb_counts,
        "simulation": simulation,
    }
