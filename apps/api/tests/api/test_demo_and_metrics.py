"""M9 tests: sandbox isolation, advance-time, reset, internal/tick, R6 metrics & simulation."""
import logging
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import utc_now
from app.db.models import Sandbox
from app.db.session import get_engine, init_db, reset_engine
from app.main import create_app

logger = logging.getLogger(__name__)


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    db_url = f"sqlite:///{(tmp_path / 'm9_demo.db').as_posix()}"
    eng = reset_engine(db_url)
    init_db(eng)
    return TestClient(create_app())


def test_two_sandboxes_are_isolated_and_advance_time_creates_overdue(
    client: TestClient,
) -> None:
    """Two sandboxes are isolated; advancing time in sandbox 1 does not affect sandbox 2."""
    tok1 = client.post("/api/v1/sandbox").json()["token"]
    tok2 = client.post("/api/v1/sandbox").json()["token"]
    h1 = {"X-Sandbox-Token": tok1, "X-Role": "coordinator"}
    h2 = {"X-Sandbox-Token": tok2, "X-Role": "coordinator"}

    ov1_before = client.get(
        "/api/v1/cases/priority-queue?overdue=true&page_size=50", headers=h1
    ).json()["total"]
    ov2_before = client.get(
        "/api/v1/cases/priority-queue?overdue=true&page_size=50", headers=h2
    ).json()["total"]
    assert ov1_before == ov2_before

    # Advance time by 72 hours in sandbox 1
    adv = client.post("/api/v1/demo/advance-time", headers=h1, json={"hours": 72.0})
    assert adv.status_code == 200
    assert adv.json()["clock_offset_hours"] == 72.0
    assert adv.json()["overdue_cases"] > ov1_before
    assert adv.json()["newly_breached"] > 0

    # Advancing by 0.1h again does not duplicate SLA_BREACH for already-breached cases
    adv2 = client.post("/api/v1/demo/advance-time", headers=h1, json={"hours": 0.1})
    assert adv2.status_code == 200
    assert adv2.json()["newly_breached"] == 0

    # Sandbox 2 overdue count is untouched
    ov2_after = client.get(
        "/api/v1/cases/priority-queue?overdue=true&page_size=50", headers=h2
    ).json()["total"]
    assert ov2_after == ov2_before

    # Reset sandbox 1 restores initial overdue count and offset 0.0
    rst = client.post("/api/v1/demo/reset", headers=h1)
    assert rst.status_code == 200
    assert rst.json()["clock_offset_hours"] == 0.0
    ov1_reset = client.get(
        "/api/v1/cases/priority-queue?overdue=true&page_size=50", headers=h1
    ).json()["total"]
    assert ov1_reset == ov1_before


def test_internal_tick_deletes_expired_sandboxes(client: TestClient) -> None:
    tok = client.post("/api/v1/sandbox").json()["token"]
    assert tok.startswith("sbx_")

    # Mark sandbox expired in DB
    with Session(get_engine()) as db:
        sb = db.scalar(select(Sandbox))
        assert sb is not None
        sb.expires_at = utc_now() - timedelta(hours=1)
        db.commit()

    # Unauthorized cron call -> 401
    bad = client.post("/api/v1/internal/tick", headers={"X-Cron-Token": "wrong"})
    assert bad.status_code == 401

    # Authorized cron call -> deletes expired sandbox
    ok = client.post(
        "/api/v1/internal/tick",
        headers={"X-Cron-Token": "change-me-to-a-long-random-string"},
    )
    assert ok.status_code == 200
    assert ok.json()["expired_sandboxes_deleted"] == 1


def test_r6_metrics_computed_from_events(client: TestClient) -> None:
    """R6: /metrics/summary computes state counts, intervals, rates, aging, and delay reasons."""
    tok = client.post("/api/v1/sandbox").json()["token"]
    headers = {"X-Sandbox-Token": tok, "X-Role": "coordinator"}

    res = client.get("/api/v1/metrics/summary", headers=headers)
    assert res.status_code == 200
    m = res.json()

    assert sum(m["state_counts"].values()) == 60
    expected_intervals = {
        "result_to_notified",
        "notified_to_ack",
        "ack_to_confirmatory",
        "referral_to_accept",
        "accept_to_appointment",
        "appointment_to_seen",
        "seen_to_plan",
        "result_to_closed",
    }
    assert set(m["intervals"].keys()) == expected_intervals
    assert m["intervals"]["result_to_notified"]["n"] > 0
    assert 0.0 <= m["referral_completion_rate"] <= 1.0
    assert 0.0 <= m["appointment_completion_rate"] <= 1.0
    assert 0.0 <= m["documented_closure_rate"] <= 1.0
    assert 0.0 <= m["acknowledgement_rate"] <= 1.0
    assert m["unresolved"]["total"] == 50  # 60 total minus 10 closed (archetypes 11 & 12)
    assert len(m["delay_reasons"]) >= 1
    assert set(m["teachback"].keys()) == {"understood", "partial", "confused"}


def test_r6_simulation_report_generated(client: TestClient) -> None:
    """R6: Labeled 100-run queue simulation compares FIFO vs CareLoop priority with 95% CIs."""
    tok = client.post("/api/v1/sandbox").json()["token"]
    headers = {"X-Sandbox-Token": tok, "X-Role": "coordinator"}

    m = client.get("/api/v1/metrics/summary", headers=headers).json()
    sim = m["simulation"]

    assert sim["runs"] == 100
    assert sim["careloop"]["median_days"] < sim["fifo"]["median_days"]
    assert sim["careloop"]["unresolved_day60"] < sim["fifo"]["unresolved_day60"]
    assert len(sim["ci95"]["careloop_median_days"]) == 2
    assert len(sim["ci95"]["fifo_median_days"]) == 2
