"""M1 domain unit tests (pure Python, no database): transitions, SLA, closure, priority, metrics."""
import logging
from datetime import UTC, datetime, timedelta

from app.core.clock import make_clock
from app.domain.closure import can_close
from app.domain.metrics import compute_metrics_summary
from app.domain.priority import compute_case_priority, evaluate_escalation, priority
from app.domain.sla import (
    hours_remaining,
    is_overdue,
    sla_due_at,
    sla_hours_for,
    sla_pressure,
)
from app.domain.states import (
    ALL_STATES,
    ALLOWED_CLOSURE_EVIDENCE,
    NON_CLOSED_STATES,
    CaseState,
    EvidenceType,
    Role,
    UrgencyTier,
    resolve_language,
)
from app.domain.transitions import (
    LEGAL_TRANSITIONS,
    STATE_SPECS,
    is_legal_transition,
    owner_role_for_state,
    validate_transition,
)

logger = logging.getLogger(__name__)


def test_r2_each_state_has_owner_and_sla() -> None:
    """Every non-closed state must define an owner_role and positive SLA hours."""
    expected = {
        CaseState.RESULT_ISSUED: (Role.CLINICIAN, 24),
        CaseState.PATIENT_NOTIFIED: (Role.COORDINATOR, 48),
        CaseState.ACKNOWLEDGED: (Role.COORDINATOR, 120),
        CaseState.CONFIRMATORY_PENDING: (Role.CLINICIAN, 336),
        CaseState.REFERRAL_SENT: (Role.CLINICIAN, 72),
        CaseState.REJECTED: (Role.COORDINATOR, 24),
        CaseState.REFERRAL_ACCEPTED: (Role.CLINICIAN, 120),
        CaseState.APPOINTMENT_BOOKED: (Role.COORDINATOR, 168),
        CaseState.SEEN: (Role.CLINICIAN, 72),
        CaseState.TREATMENT_OR_SURVEILLANCE: (Role.CLINICIAN, 720),
    }
    for st in NON_CLOSED_STATES:
        spec = STATE_SPECS[st]
        exp_role, exp_hours = expected[st]
        assert spec.owner_role == exp_role
        assert spec.base_sla_hours == exp_hours
        assert owner_role_for_state(st) == exp_role.value
        assert sla_hours_for(st, UrgencyTier.ROUTINE) == float(exp_hours)
        # Urgent tier halves SLA hours
        assert sla_hours_for(st, UrgencyTier.URGENT) == float(exp_hours) / 2.0

    closed_spec = STATE_SPECS[CaseState.CLOSED]
    assert closed_spec.owner_role is None
    assert closed_spec.base_sla_hours is None
    assert sla_hours_for(CaseState.CLOSED, UrgencyTier.URGENT) is None


def test_every_legal_and_illegal_transition_pair() -> None:
    """Exhaustively check all 11x11 state pairs against LEGAL_TRANSITIONS."""
    for src in ALL_STATES:
        for dst in ALL_STATES:
            expected_legal = dst in LEGAL_TRANSITIONS[src]
            assert is_legal_transition(src, dst) is expected_legal
            if not expected_legal:
                ok, msg = validate_transition(src, dst, EvidenceType.MESSAGE_SENT.value)
                assert not ok
                assert "illegal transition" in msg


def test_entry_evidence_required_for_transitions() -> None:
    ok, _ = validate_transition(
        CaseState.RESULT_ISSUED, CaseState.PATIENT_NOTIFIED, EvidenceType.MESSAGE_SENT.value
    )
    assert ok
    ok_missing, msg = validate_transition(
        CaseState.RESULT_ISSUED, CaseState.PATIENT_NOTIFIED, None
    )
    assert not ok_missing
    assert "requires evidence" in msg

    # REJECTED requires referral_rejected AND reason_code
    ok_no_reason, _ = validate_transition(
        CaseState.REFERRAL_SENT, CaseState.REJECTED, EvidenceType.REFERRAL_REJECTED.value, None
    )
    assert not ok_no_reason
    ok_with_reason, _ = validate_transition(
        CaseState.REFERRAL_SENT,
        CaseState.REJECTED,
        EvidenceType.REFERRAL_REJECTED.value,
        "referral_rejected_capacity",
    )
    assert ok_with_reason


def test_sla_clock_and_advance_time_offset() -> None:
    t0 = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    base_clock = lambda: t0  # noqa: E731
    # RESULT_ISSUED routine SLA is 24h; urgent is 12h
    assert sla_due_at(CaseState.RESULT_ISSUED, t0, 3) == t0 + timedelta(hours=24)
    assert sla_due_at(CaseState.RESULT_ISSUED, t0, 1) == t0 + timedelta(hours=12)

    clock_10h = make_clock(10.0, base_clock=base_clock)
    assert not is_overdue(CaseState.RESULT_ISSUED, t0, 1, clock=clock_10h)
    assert hours_remaining(CaseState.RESULT_ISSUED, t0, 1, clock=clock_10h) == 2.0

    clock_15h = make_clock(15.0, base_clock=base_clock)
    assert is_overdue(CaseState.RESULT_ISSUED, t0, 1, clock=clock_15h)
    assert sla_pressure(CaseState.RESULT_ISSUED, t0, 1, clock=clock_15h) == 15.0 / 12.0


def test_closure_gate_paths() -> None:
    for ev in ALLOWED_CLOSURE_EVIDENCE:
        ok, kind = can_close({ev}, None)
        assert ok and kind == "evidence"

    ok_bad, msg = can_close({EvidenceType.MESSAGE_SENT.value}, None)
    assert not ok_bad
    assert msg == "closure requires evidence or an authorized override"

    ok_unauth, _ = can_close(set(), {"authorized": False, "reason": "clinical judgment"})
    assert not ok_unauth

    ok_no_reason, _ = can_close(set(), {"authorized": True, "reason": ""})
    assert not ok_no_reason

    ok_ovr, kind_ovr = can_close(
        set(), {"authorized": True, "reason": "transferred out of network"}
    )
    assert ok_ovr and kind_ovr == "authorized_override"


def test_priority_ordering_and_never_lowers_care() -> None:
    p_low_risk = compute_case_priority(urgency_tier=2, p_dropoff=0.10, sla_pressure_val=0.3)
    p_high_risk = compute_case_priority(urgency_tier=2, p_dropoff=0.80, sla_pressure_val=0.3)
    assert p_high_risk > p_low_risk

    p_urgent = compute_case_priority(urgency_tier=1, p_dropoff=0.20, sla_pressure_val=0.1)
    assert p_urgent > 10.0
    assert p_urgent > p_high_risk

    # Pressure caps at 1.5
    p_cap1 = priority(0.6, 0.5, 1.5, False)
    p_cap2 = priority(0.6, 0.5, 3.0, False)
    assert p_cap1 == p_cap2


def test_escalation_rules() -> None:
    esc, reasons = evaluate_escalation(
        urgency_tier=1, overdue=True, p_dropoff=0.2
    )
    assert esc and "urgent_and_overdue" in reasons

    esc2, reasons2 = evaluate_escalation(
        urgency_tier=3, overdue=False, p_dropoff=0.70, teachback_label="confused", ads=0.6
    )
    assert esc2
    assert {"high_dropoff_risk", "teachback_confused", "high_ads_divergence"} <= set(reasons2)

    esc_no, _ = evaluate_escalation(urgency_tier=2, overdue=True, p_dropoff=0.4)
    assert not esc_no


def test_language_fallback() -> None:
    assert resolve_language("en") == ("en", False)
    assert resolve_language("hi") == ("hi", False)
    assert resolve_language("es") == ("es", False)
    assert resolve_language("fr") == ("en", True)


def test_metrics_summary_from_events() -> None:
    t0 = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    cases = [
        {"id": "c1", "state": "CLOSED", "created_at": t0, "acknowledged": True},
        {"id": "c2", "state": "PATIENT_NOTIFIED", "created_at": t0, "acknowledged": False},
    ]
    events = [
        {"case_id": "c1", "to_state": "RESULT_ISSUED", "at": t0},
        {"case_id": "c1", "to_state": "PATIENT_NOTIFIED", "at": t0 + timedelta(hours=4)},
        {"case_id": "c1", "to_state": "ACKNOWLEDGED", "at": t0 + timedelta(hours=10)},
        {"case_id": "c1", "to_state": "CLOSED", "at": t0 + timedelta(hours=100)},
    ]
    summary = compute_metrics_summary(
        cases=cases,
        events=events,
        referrals=[{"status": "accepted"}, {"status": "rejected"}],
        closures=[{"kind": "evidence"}],
        delay_reasons=[{"code": "transport_barrier"}],
        messages=[{"teachback_label": "understood"}],
        simulation={"runs": 100},
        clock=lambda: t0 + timedelta(days=10),
    )
    assert summary["intervals"]["result_to_notified"]["median_hours"] == 4.0
    assert summary["referral_completion_rate"] == 0.5
    assert summary["documented_closure_rate"] == 1.0
    assert summary["unresolved"]["total"] == 1
