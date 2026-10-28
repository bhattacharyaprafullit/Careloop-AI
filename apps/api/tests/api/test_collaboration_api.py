"""M8 collaboration tests (R3, R4, R5) and full RESULT_ISSUED -> CLOSED walkthrough."""
import logging
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.db.session import init_db, reset_engine
from app.main import create_app

logger = logging.getLogger(__name__)


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    db_url = f"sqlite:///{(tmp_path / 'm8_collab.db').as_posix()}"
    eng = reset_engine(db_url)
    init_db(eng)
    return TestClient(create_app())


def test_r3_confused_teachback_escalates(client: TestClient) -> None:
    """R3: Confused or empty teach-back reply sets escalated=True and queues approval."""
    token = client.post("/api/v1/sandbox").json()["token"]
    coord = {"X-Sandbox-Token": token, "X-Role": "coordinator"}

    # Pick a non-escalated case in PATIENT_NOTIFIED or CONFIRMATORY_PENDING
    q = client.get(
        "/api/v1/cases/priority-queue?state=CONFIRMATORY_PENDING", headers=coord
    ).json()
    cid = q["items"][0]["case_id"]
    det = client.get(f"/api/v1/cases/{cid}/details", headers=coord).json()
    pt_token = det["case"]["patient_token"]
    assert det["case"]["escalated"] is False

    # Patient views portal in Hindi and Spanish
    p_hi = client.get(f"/api/v1/patient/{pt_token}?lang=hi")
    assert p_hi.status_code == 200
    assert p_hi.json()["language"] == "hi"

    # Patient submits confused teachback
    tb = client.post(
        f"/api/v1/patient/{pt_token}/teachback",
        json={"reply_text": "I am confused and do not know what test I need."},
    )
    assert tb.status_code == 200
    assert tb.json()["label"] == "confused"
    assert tb.json()["escalated"] is True

    det_after = client.get(f"/api/v1/cases/{cid}/details", headers=coord).json()
    assert det_after["case"]["escalated"] is True
    assert det_after["pending_approval"] is not None


def test_r4_reject_requeues_to_coordinator(client: TestClient) -> None:
    """R4: Rejecting a referral requires reason_code, moves to REJECTED, and assigns coordinator."""
    token = client.post("/api/v1/sandbox").json()["token"]
    clin = {"X-Sandbox-Token": token, "X-Role": "clinician"}

    refs = client.get("/api/v1/referrals?status_filter=sent", headers=clin).json()["items"]
    assert len(refs) >= 1
    ref_id = refs[0]["id"]

    # Reject without reason_code -> 400
    bad = client.post(
        f"/api/v1/referrals/{ref_id}/decision",
        headers=clin,
        json={"decision": "reject"},
    )
    assert bad.status_code == 400

    # Reject with reason_code -> moves to REJECTED owned by coordinator and escalates
    ok = client.post(
        f"/api/v1/referrals/{ref_id}/decision",
        headers=clin,
        json={"decision": "reject", "reason_code": "referral_rejected_capacity"},
    )
    assert ok.status_code == 200
    data = ok.json()
    assert data["state"] == "REJECTED"
    assert data["owner_role"] == "coordinator"
    assert data["escalated"] is True


def test_r4_consult_thread_writes_events(client: TestClient) -> None:
    """R4: Creating and replying to a consult thread writes CONSULT_CREATED and CONSULT_REPLIED."""
    token = client.post("/api/v1/sandbox").json()["token"]
    coord = {"X-Sandbox-Token": token, "X-Role": "coordinator"}
    clin = {"X-Sandbox-Token": token, "X-Role": "clinician"}

    q = client.get("/api/v1/cases/priority-queue?page_size=5", headers=coord).json()
    cid = q["items"][0]["case_id"]

    c_res = client.post(
        "/api/v1/consults",
        headers=coord,
        json={
            "case_id": cid,
            "kind": "clinician_to_clinician",
            "message": "Need specialist input on diagnostic interval.",
        },
    )
    assert c_res.status_code == 201
    con_id = c_res.json()["consult_id"]

    r_res = client.post(
        f"/api/v1/consults/{con_id}/reply",
        headers=clin,
        json={"message": "Proceed with diagnostic colposcopy within 2 weeks."},
    )
    assert r_res.status_code == 200
    assert r_res.json()["status"] == "answered"
    assert len(r_res.json()["thread"]) == 2

    det = client.get(f"/api/v1/cases/{cid}/details", headers=coord).json()
    ev_types = [t["event_type"] for t in det["timeline"]]
    assert "CONSULT_CREATED" in ev_types
    assert "CONSULT_REPLIED" in ev_types


def test_r5_close_blocked_without_evidence(client: TestClient) -> None:
    """R5: Closing a case without closure evidence or override returns 409 closure_blocked."""
    token = client.post("/api/v1/sandbox").json()["token"]
    clin = {"X-Sandbox-Token": token, "X-Role": "clinician"}

    # Pick a SEEN case (archetype 9: no closure evidence recorded yet)
    q = client.get("/api/v1/cases/priority-queue?state=SEEN", headers=clin).json()
    cid = q["items"][0]["case_id"]

    blocked = client.post(f"/api/v1/cases/{cid}/close", headers=clin, json={})
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "closure_blocked"

    # Non-closure evidence (message_sent) is also blocked
    blocked2 = client.post(
        f"/api/v1/cases/{cid}/close",
        headers=clin,
        json={"evidence_type": "message_sent"},
    )
    assert blocked2.status_code == 409
    assert blocked2.json()["error"]["code"] == "closure_blocked"


def test_r5_override_needs_reason_and_role(client: TestClient) -> None:
    """R5: Closure override requires clinician role AND a non-empty reason."""
    token = client.post("/api/v1/sandbox").json()["token"]
    coord = {"X-Sandbox-Token": token, "X-Role": "coordinator"}
    clin = {"X-Sandbox-Token": token, "X-Role": "clinician"}

    q = client.get("/api/v1/cases/priority-queue?state=SEEN", headers=clin).json()
    cid = q["items"][0]["case_id"]

    # Coordinator cannot authorize an override -> 409
    bad_role = client.post(
        f"/api/v1/cases/{cid}/close",
        headers=coord,
        json={"override": {"reason": "Transferred care"}},
    )
    assert bad_role.status_code == 409
    assert bad_role.json()["error"]["code"] == "closure_blocked"

    # Clinician with empty reason -> 409
    bad_reason = client.post(
        f"/api/v1/cases/{cid}/close",
        headers=clin,
        json={"override": {"reason": "   "}},
    )
    assert bad_reason.status_code == 409
    assert bad_reason.json()["error"]["code"] == "closure_blocked"

    # Clinician with valid reason -> 200 CLOSED
    ok = client.post(
        f"/api/v1/cases/{cid}/close",
        headers=clin,
        json={"override": {"reason": "Confirmed surgical treatment at external hospital"}},
    )
    assert ok.status_code == 200
    assert ok.json()["state"] == "CLOSED"
    assert ok.json()["kind"] == "override"


def test_walk_case_from_result_issued_to_closed_all_roles(client: TestClient) -> None:
    """Walk one case from RESULT_ISSUED to CLOSED using clinician, coordinator, and patient."""
    token = client.post("/api/v1/sandbox").json()["token"]
    clin = {"X-Sandbox-Token": token, "X-Role": "clinician"}
    coord = {"X-Sandbox-Token": token, "X-Role": "coordinator"}

    # Start from archetype 1: RESULT_ISSUED
    q = client.get(
        "/api/v1/cases/priority-queue?state=RESULT_ISSUED", headers=clin
    ).json()
    cid = q["items"][0]["case_id"]
    det0 = client.get(f"/api/v1/cases/{cid}/details", headers=clin).json()
    pt_token = det0["case"]["patient_token"]

    # Early close attempt from RESULT_ISSUED without override -> 409
    early = client.post(
        f"/api/v1/cases/{cid}/close",
        headers=clin,
        json={"evidence_type": "treatment_started"},
    )
    assert early.status_code == 409

    # 1. Clinician advances RESULT_ISSUED -> PATIENT_NOTIFIED
    r1 = client.post(
        f"/api/v1/cases/{cid}/advance",
        headers=clin,
        json={"to_state": "PATIENT_NOTIFIED", "evidence": {"type": "message_sent", "ref": "m1"}},
    )
    assert r1.status_code == 200 and r1.json()["state"] == "PATIENT_NOTIFIED"

    # 2. Patient acknowledges -> ACKNOWLEDGED and submits understood teach-back
    r2 = client.post(f"/api/v1/patient/{pt_token}/acknowledge")
    assert r2.status_code == 200 and r2.json()["state"] == "ACKNOWLEDGED"
    tb = client.post(
        f"/api/v1/patient/{pt_token}/teachback",
        json={
            "reply_text": f"I understand my {det0['case']['screening_type']} follow-up appointment."
        },
    )
    assert tb.status_code == 200 and tb.json()["label"] == "understood"

    # 3. Coordinator orders confirmatory test -> CONFIRMATORY_PENDING
    r3 = client.post(
        f"/api/v1/cases/{cid}/advance",
        headers=coord,
        json={
            "to_state": "CONFIRMATORY_PENDING",
            "evidence": {"type": "confirmatory_ordered", "ref": "ord-1"},
        },
    )
    assert r3.status_code == 200 and r3.json()["state"] == "CONFIRMATORY_PENDING"

    # 4. Clinician sends referral with SBAR -> REFERRAL_SENT
    ref_res = client.post(
        "/api/v1/referrals",
        headers=clin,
        json={"case_id": cid, "to_org": "Metro Oncology & Diagnostics"},
    )
    assert ref_res.status_code == 201
    ref_id = ref_res.json()["referral_id"]

    # 5. Receiving clinician accepts referral -> REFERRAL_ACCEPTED
    r5 = client.post(
        f"/api/v1/referrals/{ref_id}/decision",
        headers=clin,
        json={"decision": "accept"},
    )
    assert r5.status_code == 200 and r5.json()["state"] == "REFERRAL_ACCEPTED"

    # 6. Clinician/coordinator books appointment -> APPOINTMENT_BOOKED
    r6 = client.post(
        f"/api/v1/cases/{cid}/advance",
        headers=coord,
        json={
            "to_state": "APPOINTMENT_BOOKED",
            "evidence": {"type": "appointment_booked", "ref": "apt-1"},
        },
    )
    assert r6.status_code == 200 and r6.json()["state"] == "APPOINTMENT_BOOKED"

    # 7. Coordinator records attendance -> SEEN
    r7 = client.post(
        f"/api/v1/cases/{cid}/advance",
        headers=coord,
        json={"to_state": "SEEN", "evidence": {"type": "attendance_recorded", "ref": "att-1"}},
    )
    assert r7.status_code == 200 and r7.json()["state"] == "SEEN"

    # 8. Clinician records care plan -> TREATMENT_OR_SURVEILLANCE
    r8 = client.post(
        f"/api/v1/cases/{cid}/advance",
        headers=clin,
        json={
            "to_state": "TREATMENT_OR_SURVEILLANCE",
            "evidence": {"type": "plan_recorded", "ref": "plan-1"},
        },
    )
    assert r8.status_code == 200 and r8.json()["state"] == "TREATMENT_OR_SURVEILLANCE"

    # 9. Clinician closes case with treatment_started evidence -> CLOSED
    r9 = client.post(
        f"/api/v1/cases/{cid}/close",
        headers=clin,
        json={"evidence_type": "treatment_started"},
    )
    assert r9.status_code == 200 and r9.json()["state"] == "CLOSED"
