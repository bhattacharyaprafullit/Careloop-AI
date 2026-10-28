"""Repository and seed loader for CareLoop AI (M4).

Every state change, message, decision, and LLM call writes an append-only row.
"""
import hashlib
import json
import logging
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.clock import ClockFn, make_clock, utc_now
from app.core.config import get_settings
from app.db.models import (
    Case,
    CaseEvent,
    Closure,
    Consult,
    DelayReason,
    Evidence,
    LLMOutput,
    Message,
    Patient,
    PendingApproval,
    Referral,
    RiskScore,
    Sandbox,
)

logger = logging.getLogger(__name__)

MAX_CASES_PER_SANDBOX = 250


def _uid(prefix: str = "") -> str:
    h = uuid.uuid4().hex[:16]
    return f"{prefix}-{h}" if prefix else h


def _parse_dt(val: str | datetime | None) -> datetime | None:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val if val.tzinfo else val.replace(tzinfo=UTC)
    dt = datetime.fromisoformat(val)
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def hash_token(token: str) -> str:
    """Return SHA-256 hex digest of a sandbox or patient token."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def load_seed_data(model_dir: Path | None = None) -> dict[str, Any]:
    """Load the 60-case seed payload from ml/artifacts/seed.json."""
    mdir = model_dir or get_settings().model_dir
    seed_path = Path(mdir) / "seed.json"
    return dict(json.loads(seed_path.read_text(encoding="utf-8")))


def clone_seed_into_sandbox(
    db: Session,
    *,
    sandbox_id: str,
    token_hash: str,
    now: datetime | None = None,
    model_dir: Path | None = None,
) -> Sandbox:
    """Clone all 60 seed cases and pre-generated LLM outputs under `sandbox_id`."""
    seed = load_seed_data(model_dir)
    base_time = _parse_dt(seed["base_time"]) or utc_now()
    current_now = now or utc_now()
    shift = current_now - base_time

    sb = Sandbox(
        id=sandbox_id,
        token_hash=token_hash,
        clock_offset_hours=0.0,
        created_at=current_now,
        expires_at=current_now + timedelta(hours=24),
    )
    db.add(sb)
    db.flush()

    for item in seed["cases"]:
        idx_suffix = str(item["case_id"]).split("-")[-1]
        cid = f"{sandbox_id[:8]}-case-{idx_suffix}"
        pid = f"{sandbox_id[:8]}-pat-{idx_suffix}"
        # Patient token deterministic per sandbox + seed index so UI /p/[token] works
        pt_plain = f"pt-{sandbox_id[:8]}-{idx_suffix}"
        pt_hash = hash_token(pt_plain)

        pat_raw = item["patient"]
        db.add(
            Patient(
                id=pid,
                sandbox_id=sandbox_id,
                alias=str(pat_raw["alias"]),
                age=int(pat_raw["age"]),
                language=str(pat_raw["language"]),
                insurance=str(pat_raw["insurance"]),
                distance_miles=float(pat_raw["distance_miles"]),
                portal_active=bool(pat_raw["portal_active"]),
                prior_noshow_count=int(pat_raw["prior_noshow_count"]),
                prior_noshow_ratio=float(pat_raw["prior_noshow_ratio"]),
                days_since_last_encounter=int(pat_raw["days_since_last_encounter"]),
            )
        )

        c_raw = item["case"]
        st_entered = (_parse_dt(c_raw["state_entered_at"]) or base_time) + shift
        c_created = (_parse_dt(c_raw["created_at"]) or base_time) + shift
        parsed_closed = _parse_dt(c_raw.get("closed_at"))
        c_closed = (parsed_closed + shift) if parsed_closed is not None else None

        db.add(
            Case(
                id=cid,
                sandbox_id=sandbox_id,
                patient_id=pid,
                screening_type=str(c_raw["screening_type"]),
                severity_grade=int(c_raw["severity_grade"]),
                urgency_tier=int(c_raw["urgency_tier"]),
                state=str(c_raw["state"]),
                state_entered_at=st_entered,
                owner_role=c_raw.get("owner_role"),
                owner_id=c_raw.get("owner_id"),
                escalated=bool(c_raw["escalated"]),
                finding_to_order_days=float(c_raw["finding_to_order_days"]),
                scheduling_lead_time=float(c_raw["scheduling_lead_time"]),
                contact_attempts=int(c_raw["contact_attempts"]),
                acknowledged=bool(c_raw["acknowledged"]),
                patient_token_hash=pt_hash,
                created_at=c_created,
                closed_at=c_closed,
            )
        )

        r_raw = item["risk"]
        db.add(
            RiskScore(
                id=_uid("rs"),
                sandbox_id=sandbox_id,
                case_id=cid,
                stage=str(r_raw["stage"]),
                p_dropoff=float(r_raw["p_dropoff"]),
                median_days=float(r_raw["median_days"]),
                p_open_30=float(r_raw["p_open_30"]),
                p_open_60=float(r_raw["p_open_60"]),
                p_open_90=float(r_raw["p_open_90"]),
                shap=dict(r_raw["shap"]),
                survival_curve=list(r_raw["survival_curve"]),
                model_version=str(r_raw["model_version"]),
                at=st_entered,
            )
        )

        for ev in item["events"]:
            ev_at = (_parse_dt(ev["at"]) or base_time) + shift
            payload = dict(ev.get("payload") or {})
            payload["patient_token"] = pt_plain
            db.add(
                CaseEvent(
                    id=_uid("ev"),
                    sandbox_id=sandbox_id,
                    case_id=cid,
                    event_type=str(ev["event_type"]),
                    from_state=ev.get("from_state"),
                    to_state=ev.get("to_state"),
                    actor_role=str(ev["actor_role"]),
                    actor_id=ev.get("actor_id"),
                    payload=payload,
                    at=ev_at,
                )
            )

        for evd in item["evidence"]:
            evd_at = (_parse_dt(evd["at"]) or base_time) + shift
            db.add(
                Evidence(
                    id=_uid("evd"),
                    sandbox_id=sandbox_id,
                    case_id=cid,
                    type=str(evd["type"]),
                    ref=str(evd["ref"]),
                    created_by=str(evd["created_by"]),
                    at=evd_at,
                )
            )

        for msg in item["messages"]:
            msg_at = (_parse_dt(msg["at"]) or base_time) + shift
            db.add(
                Message(
                    id=_uid("msg"),
                    sandbox_id=sandbox_id,
                    case_id=cid,
                    channel=str(msg["channel"]),
                    language=str(msg["language"]),
                    body=str(msg["body"]).replace(item["case_id"], cid),
                    direction=str(msg["direction"]),
                    status=str(msg["status"]),
                    teachback_label=msg.get("teachback_label"),
                    at=msg_at,
                )
            )

        if item.get("referral"):
            ref = item["referral"]
            ref_created = (_parse_dt(ref["created_at"]) or base_time) + shift
            parsed_decided = _parse_dt(ref.get("decided_at"))
            ref_decided = (parsed_decided + shift) if parsed_decided is not None else None
            db.add(
                Referral(
                    id=_uid("ref"),
                    sandbox_id=sandbox_id,
                    case_id=cid,
                    from_org=str(ref["from_org"]),
                    to_org=str(ref["to_org"]),
                    status=str(ref["status"]),
                    reason_code=ref.get("reason_code"),
                    sbar=dict(ref["sbar"]),
                    created_at=ref_created,
                    decided_at=ref_decided,
                )
            )

        for con in item.get("consults", []):
            con_at = (_parse_dt(con["created_at"]) or base_time) + shift
            db.add(
                Consult(
                    id=_uid("con"),
                    sandbox_id=sandbox_id,
                    case_id=cid,
                    kind=str(con["kind"]),
                    status=str(con["status"]),
                    thread=list(con["thread"]),
                    created_at=con_at,
                )
            )

        if item.get("pending_approval"):
            pa = item["pending_approval"]
            db.add(
                PendingApproval(
                    id=_uid("pa"),
                    sandbox_id=sandbox_id,
                    case_id=cid,
                    action_type=str(pa["action_type"]),
                    payload=dict(pa["payload"]),
                    reasons=list(pa["reasons"]),
                    status=str(pa["status"]),
                    at=st_entered,
                )
            )

        if item.get("closure"):
            cl = item["closure"]
            cl_at = (_parse_dt(cl["at"]) or base_time) + shift
            db.add(
                Closure(
                    id=_uid("cl"),
                    sandbox_id=sandbox_id,
                    case_id=cid,
                    kind=str(cl["kind"]),
                    evidence_type=cl.get("evidence_type"),
                    override_by=cl.get("override_by"),
                    override_reason=cl.get("override_reason"),
                    at=cl_at,
                )
            )

        for dr in item.get("delay_reasons", []):
            db.add(
                DelayReason(
                    id=_uid("dr"),
                    sandbox_id=sandbox_id,
                    case_id=cid,
                    code=str(dr["code"]),
                    proposed_by=str(dr["proposed_by"]),
                    confirmed=bool(dr["confirmed"]),
                    at=st_entered,
                )
            )

        for lo in item.get("llm_outputs", []):
            out_copy = json.loads(
                json.dumps(lo["output"]).replace(item["case_id"], cid)
            )
            db.add(
                LLMOutput(
                    id=_uid("llm"),
                    sandbox_id=sandbox_id,
                    case_id=cid,
                    kind=str(lo["kind"]),
                    input_hash=hashlib.sha256(
                        f"{lo['kind']}:{cid}".encode()
                    ).hexdigest(),
                    output=out_copy,
                    source=str(lo["source"]),
                    faithful_ok=bool(lo["faithful_ok"]),
                    ads=float(lo["ads"]) if lo.get("ads") is not None else 0.0,
                    at=st_entered,
                )
            )

    db.commit()
    db.refresh(sb)
    return sb


def create_sandbox_with_seed(
    db: Session, model_dir: Path | None = None
) -> tuple[str, Sandbox, int]:
    """Generate a new sandbox token, clone the 60 seed cases, and return (token, sandbox, 60)."""
    raw_token = f"sbx_{secrets.token_urlsafe(24)}"
    token_hash = hash_token(raw_token)
    sandbox_id = _uid("sbx")
    sb = clone_seed_into_sandbox(
        db, sandbox_id=sandbox_id, token_hash=token_hash, model_dir=model_dir
    )
    return raw_token, sb, 60


def purge_sandbox_data(db: Session, sandbox_id: str) -> None:
    """Delete a sandbox and all its child rows (deletes Sandbox first to satisfy triggers)."""
    db.execute(delete(Sandbox).where(Sandbox.id == sandbox_id))
    for model_cls in (
        CaseEvent,
        Closure,
        LLMOutput,
        Evidence,
        RiskScore,
        Referral,
        Consult,
        Message,
        PendingApproval,
        DelayReason,
        Case,
        Patient,
    ):
        db.execute(delete(model_cls).where(model_cls.sandbox_id == sandbox_id))
    db.commit()


def get_sandbox_by_token(db: Session, token: str) -> Sandbox | None:
    """Look up an active (non-expired) sandbox by its plain token."""
    th = hash_token(token)
    sb = db.scalar(select(Sandbox).where(Sandbox.token_hash == th))
    if sb is None:
        return None
    now = utc_now()
    exp = sb.expires_at if sb.expires_at.tzinfo else sb.expires_at.replace(tzinfo=UTC)
    if exp < now:
        return None
    return sb


def clock_for_sandbox(sb: Sandbox) -> ClockFn:
    """Return an injectable clock shifted by `sb.clock_offset_hours`."""
    return make_clock(float(sb.clock_offset_hours))


def append_case_event(
    db: Session,
    *,
    sandbox_id: str,
    case_id: str,
    event_type: str,
    actor_role: str,
    actor_id: str | None = None,
    from_state: str | None = None,
    to_state: str | None = None,
    payload: dict[str, Any] | None = None,
    at: datetime | None = None,
) -> CaseEvent:
    """Insert an immutable row into case_events."""
    ev = CaseEvent(
        id=_uid("ev"),
        sandbox_id=sandbox_id,
        case_id=case_id,
        event_type=event_type,
        from_state=from_state,
        to_state=to_state,
        actor_role=actor_role,
        actor_id=actor_id,
        payload=payload or {},
        at=at or utc_now(),
    )
    db.add(ev)
    return ev
