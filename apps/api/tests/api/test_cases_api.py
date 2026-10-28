"""M5 API tests (R1, R2): sandbox, priority-queue filters, details, ingest, assign, advance, SSE."""
import logging
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.db.session import init_db, reset_engine
from app.domain.states import ALL_STATES
from app.main import create_app

logger = logging.getLogger(__name__)


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    db_url = f"sqlite:///{(tmp_path / 'm5_api.db').as_posix()}"
    eng = reset_engine(db_url)
    init_db(eng)
    app = create_app()
    return TestClient(app)


def _create_sandbox(client: TestClient) -> str:
    res = client.post("/api/v1/sandbox")
    assert res.status_code == 201
    data = res.json()
    assert data["case_count"] == 60
    return str(data["token"])


def test_r1_timeline_covers_every_state(client: TestClient) -> None:
    """R1: Across the 60 seed cases, every one of the 11 states is visible in timelines."""
    token = _create_sandbox(client)
    headers = {"X-Sandbox-Token": token, "X-Role": "coordinator"}

    q1 = client.get("/api/v1/cases/priority-queue?page=1&page_size=50", headers=headers).json()
    q2 = client.get("/api/v1/cases/priority-queue?page=2&page_size=50", headers=headers).json()
    all_items = q1["items"] + q2["items"]
    assert len(all_items) == 60

    observed_states: set[str] = set()
    for item in all_items:
        observed_states.add(item["state"])
        det = client.get(f"/api/v1/cases/{item['case_id']}/details", headers=headers)
        assert det.status_code == 200
        body = det.json()
        for t in body["timeline"]:
            if t["to_state"]:
                observed_states.add(t["to_state"])

    expected = {s.value for s in ALL_STATES}
    assert observed_states == expected


def test_r2_overdue_unassigned_rejected_filters(client: TestClient) -> None:
    """R2: Overdue, unassigned, rejected, and needs_approval filters return exact matching cases."""
    token = _create_sandbox(client)
    headers = {"X-Sandbox-Token": token, "X-Role": "coordinator"}

    ov = client.get(
        "/api/v1/cases/priority-queue?overdue=true&page_size=50", headers=headers
    ).json()
    assert ov["total"] >= 5
    assert all(it["overdue"] is True for it in ov["items"])

    un = client.get(
        "/api/v1/cases/priority-queue?unassigned=true&page_size=50", headers=headers
    ).json()
    assert un["total"] >= 5
    assert all(it["owner_id"] is None for it in un["items"])

    rj = client.get(
        "/api/v1/cases/priority-queue?rejected=true&page_size=50", headers=headers
    ).json()
    assert rj["total"] == 5
    assert all(it["state"] == "REJECTED" for it in rj["items"])

    na = client.get(
        "/api/v1/cases/priority-queue?needs_approval=true&page_size=50", headers=headers
    ).json()
    assert na["total"] >= 10
    assert all(it["needs_approval"] is True for it in na["items"])


def test_ingest_assign_advance_and_stream(client: TestClient) -> None:
    token = _create_sandbox(client)
    headers = {"X-Sandbox-Token": token, "X-Role": "clinician"}

    ing = client.post(
        "/api/v1/screenings/ingest",
        headers=headers,
        json={
            "patient": {
                "alias": "PT-999",
                "age": 61,
                "language": "es",
                "insurance": "MEDICAID",
                "distance_miles": 24.0,
                "portal_active": False,
                "prior_noshow_count": 3,
                "prior_noshow_ratio": 0.5,
                "days_since_last_encounter": 120,
            },
            "screening_type": "FIT",
            "severity_grade": 4,
            "urgent_flag": True,
            "finding_to_order_days": 6.0,
            "scheduling_lead_time": 28.0,
        },
    )
    assert ing.status_code == 201
    cid = ing.json()["case_id"]
    assert ing.json()["state"] == "RESULT_ISSUED"

    # Assign owner
    asg = client.post(
        f"/api/v1/cases/{cid}/assign",
        headers=headers,
        json={"owner_role": "clinician", "owner_id": "clin-9"},
    )
    assert asg.status_code == 200
    assert asg.json()["owner_id"] == "clin-9"

    # Illegal transition (RESULT_ISSUED -> SEEN) must return 409
    bad = client.post(
        f"/api/v1/cases/{cid}/advance",
        headers=headers,
        json={"to_state": "SEEN", "evidence": {"type": "attendance_recorded", "ref": "r1"}},
    )
    assert bad.status_code == 409
    assert bad.json()["error"]["code"] == "illegal_transition"

    # Legal transition with wrong evidence must return 409
    bad_ev = client.post(
        f"/api/v1/cases/{cid}/advance",
        headers=headers,
        json={"to_state": "PATIENT_NOTIFIED", "evidence": {"type": "call_log", "ref": "r2"}},
    )
    assert bad_ev.status_code == 409

    # Legal transition with valid evidence succeeds
    ok = client.post(
        f"/api/v1/cases/{cid}/advance",
        headers=headers,
        json={"to_state": "PATIENT_NOTIFIED", "evidence": {"type": "message_sent", "ref": "msg-1"}},
    )
    assert ok.status_code == 200
    assert ok.json()["state"] == "PATIENT_NOTIFIED"
    assert ok.json()["owner_role"] == "coordinator"

    # SSE stream works via query param token
    stream_res = client.get(f"/api/v1/cases/{cid}/stream?token={token}")
    assert stream_res.status_code == 200
    assert "event: status" in stream_res.text
    assert "event: done" in stream_res.text
