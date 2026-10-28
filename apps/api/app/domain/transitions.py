"""Legal state transitions and required entry evidence per state."""
import logging
from dataclasses import dataclass

from app.domain.states import CaseState, EvidenceType, Role

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StateSpec:
    owner_role: Role | None
    base_sla_hours: int | None
    required_entry_evidence: frozenset[str]


STATE_SPECS: dict[CaseState, StateSpec] = {
    CaseState.RESULT_ISSUED: StateSpec(Role.CLINICIAN, 24, frozenset()),
    CaseState.PATIENT_NOTIFIED: StateSpec(
        Role.COORDINATOR, 48, frozenset({EvidenceType.MESSAGE_SENT.value})
    ),
    CaseState.ACKNOWLEDGED: StateSpec(
        Role.COORDINATOR,
        120,
        frozenset({EvidenceType.ACKNOWLEDGEMENT.value, EvidenceType.CALL_LOG.value}),
    ),
    CaseState.CONFIRMATORY_PENDING: StateSpec(
        Role.CLINICIAN, 336, frozenset({EvidenceType.CONFIRMATORY_ORDERED.value})
    ),
    CaseState.REFERRAL_SENT: StateSpec(
        Role.CLINICIAN, 72, frozenset({EvidenceType.REFERRAL_CREATED.value})
    ),
    CaseState.REJECTED: StateSpec(
        Role.COORDINATOR, 24, frozenset({EvidenceType.REFERRAL_REJECTED.value})
    ),
    CaseState.REFERRAL_ACCEPTED: StateSpec(
        Role.CLINICIAN, 120, frozenset({EvidenceType.REFERRAL_ACCEPTED.value})
    ),
    CaseState.APPOINTMENT_BOOKED: StateSpec(
        Role.COORDINATOR, 168, frozenset({EvidenceType.APPOINTMENT_BOOKED.value})
    ),
    CaseState.SEEN: StateSpec(
        Role.CLINICIAN, 72, frozenset({EvidenceType.ATTENDANCE_RECORDED.value})
    ),
    CaseState.TREATMENT_OR_SURVEILLANCE: StateSpec(
        Role.CLINICIAN, 720, frozenset({EvidenceType.PLAN_RECORDED.value})
    ),
    CaseState.CLOSED: StateSpec(None, None, frozenset()),
}

LEGAL_TRANSITIONS: dict[CaseState, frozenset[CaseState]] = {
    CaseState.RESULT_ISSUED: frozenset({CaseState.PATIENT_NOTIFIED}),
    CaseState.PATIENT_NOTIFIED: frozenset({CaseState.ACKNOWLEDGED}),
    CaseState.ACKNOWLEDGED: frozenset(
        {CaseState.CONFIRMATORY_PENDING, CaseState.REFERRAL_SENT}
    ),
    CaseState.CONFIRMATORY_PENDING: frozenset(
        {CaseState.REFERRAL_SENT, CaseState.CLOSED}
    ),
    CaseState.REFERRAL_SENT: frozenset(
        {CaseState.REFERRAL_ACCEPTED, CaseState.REJECTED}
    ),
    CaseState.REJECTED: frozenset({CaseState.REFERRAL_SENT}),
    CaseState.REFERRAL_ACCEPTED: frozenset({CaseState.APPOINTMENT_BOOKED}),
    # APPOINTMENT_BOOKED -> SEEN, or stays on a missed visit with a rebook event
    CaseState.APPOINTMENT_BOOKED: frozenset(
        {CaseState.SEEN, CaseState.APPOINTMENT_BOOKED}
    ),
    CaseState.SEEN: frozenset(
        {CaseState.TREATMENT_OR_SURVEILLANCE, CaseState.CLOSED}
    ),
    CaseState.TREATMENT_OR_SURVEILLANCE: frozenset({CaseState.CLOSED}),
    CaseState.CLOSED: frozenset(),
}


def is_legal_transition(from_state: str | CaseState, to_state: str | CaseState) -> bool:
    """Return True only if `from_state -> to_state` is in LEGAL_TRANSITIONS."""
    try:
        src = CaseState(from_state)
        dst = CaseState(to_state)
    except ValueError:
        return False
    return dst in LEGAL_TRANSITIONS.get(src, frozenset())


def validate_transition(
    from_state: str | CaseState,
    to_state: str | CaseState,
    evidence_type: str | None = None,
    reason_code: str | None = None,
) -> tuple[bool, str]:
    """Validate transition legality and required entry evidence.

    Note: Transitioning to CLOSED must go through the closure gate (`can_close`),
    though `is_legal_transition` checks whether the source state can reach CLOSED.
    """
    try:
        src = CaseState(from_state)
        dst = CaseState(to_state)
    except ValueError:
        return False, "invalid state"

    if dst not in LEGAL_TRANSITIONS.get(src, frozenset()):
        return False, f"illegal transition from {src.value} to {dst.value}"

    if dst == CaseState.CLOSED:
        return True, "closure_gate_required"

    spec = STATE_SPECS[dst]
    if spec.required_entry_evidence and (
        not evidence_type or evidence_type not in spec.required_entry_evidence
    ):
        allowed = ", ".join(sorted(spec.required_entry_evidence))
        return False, f"state {dst.value} requires evidence in [{allowed}]"

    if dst == CaseState.REJECTED and not reason_code:
        return False, "state REJECTED requires a reason_code"

    return True, "ok"


def owner_role_for_state(state: str | CaseState) -> str | None:
    """Return the default owner role string for a given state (None for CLOSED)."""
    role = STATE_SPECS[CaseState(state)].owner_role
    return role.value if role else None
