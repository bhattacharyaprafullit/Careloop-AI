"""M7 LangGraph tests: test_r5_graph_pauses_and_resumes_once including a process restart."""
import logging
import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Case, CaseEvent, PendingApproval
from app.db.session import get_engine, init_db, reset_engine
from app.graph.checkpoint import reset_checkpointer
from app.graph.runner import run_case_graph
from app.main import create_app

logger = logging.getLogger(__name__)


def test_r5_graph_pauses_and_resumes_once(tmp_path: Path) -> None:
    """R5: Escalated case pauses at hitl_gate, survives a process restart, and resumes once."""
    db_file = tmp_path / "m7_graph.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    eng = reset_engine(db_url)
    init_db(eng)
    reset_checkpointer(db_url)

    app = create_app()
    client = TestClient(app)

    sb_res = client.post("/api/v1/sandbox")
    assert sb_res.status_code == 201
    token = sb_res.json()["token"]
    headers = {"X-Sandbox-Token": token, "X-Role": "coordinator"}

    # Pick an escalated seed case (e.g., archetype 6 REJECTED)
    q = client.get("/api/v1/cases/priority-queue?rejected=true", headers=headers).json()
    case_id = q["items"][0]["case_id"]

    with Session(get_engine()) as db:
        c = db.scalar(select(Case).where(Case.id == case_id))
        assert c is not None
        sandbox_id = c.sandbox_id

    # Run graph: must pause at hitl_gate
    run_res = run_case_graph(case_id, sandbox_id, checkpointer=reset_checkpointer(db_url))
    assert run_res["status"] == "paused"
    assert "hitl_gate" in run_res["next"]

    # Verify exactly 1 pending approval row exists for this case (idempotent upsert)
    with Session(get_engine()) as db:
        pending = list(
            db.scalars(
                select(PendingApproval).where(
                    PendingApproval.case_id == case_id,
                    PendingApproval.status == "pending",
                )
            )
        )
        assert len(pending) == 1

    # Simulate a backend process restart by resuming from a fresh Python subprocess
    resume_script = (
        "from app.db.session import reset_engine; "
        "from app.graph.checkpoint import reset_checkpointer; "
        "from app.graph.runner import resume_case_graph; "
        "from app.services.inference import load_models; "
        "from ml.data.generate import DEFAULT_ARTIFACTS_DIR; "
        f"reset_engine({db_url!r}); "
        f"ckpt = reset_checkpointer({db_url!r}); "
        "load_models(DEFAULT_ARTIFACTS_DIR); "
        f"res = resume_case_graph({case_id!r}, "
        "{'decision': 'modify', 'modified_action': {'channel': 'sms', 'owner_id': 'coord-9'}, "
        "'note': 'Reassigning after capacity rejection', 'decided_by': 'coordinator'}, "
        "checkpointer=ckpt); "
        "assert res['status'] == 'completed', res"
    )
    proc = subprocess.run(
        [sys.executable, "-c", resume_script],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, f"Subprocess resume failed: {proc.stderr}"

    # Verify ACTION_EXECUTED and GRAPH_COMPLETED were recorded exactly once
    with Session(get_engine()) as db:
        exec_events = list(
            db.scalars(
                select(CaseEvent).where(
                    CaseEvent.case_id == case_id,
                    CaseEvent.event_type == "ACTION_EXECUTED",
                )
            )
        )
        comp_events = list(
            db.scalars(
                select(CaseEvent).where(
                    CaseEvent.case_id == case_id,
                    CaseEvent.event_type == "GRAPH_COMPLETED",
                )
            )
        )
        assert len(exec_events) == 1
        assert len(comp_events) == 1


def test_workflow_resume_api_requires_note_on_modify_and_reject(tmp_path: Path) -> None:
    db_url = f"sqlite:///{(tmp_path / 'm7_api.db').as_posix()}"
    eng = reset_engine(db_url)
    init_db(eng)
    reset_checkpointer(db_url)

    client = TestClient(create_app())
    token = client.post("/api/v1/sandbox").json()["token"]
    headers = {"X-Sandbox-Token": token, "X-Role": "coordinator"}

    approvals = client.get("/api/v1/workflow/approvals", headers=headers).json()["items"]
    assert len(approvals) >= 10
    target_case = approvals[0]["case_id"]

    # Reject without note -> 400
    bad = client.post(
        "/api/v1/workflow/resume",
        headers=headers,
        json={"case_id": target_case, "decision": "reject"},
    )
    assert bad.status_code == 400
    assert bad.json()["error"]["code"] == "note_required"

    # Reject with note -> 200 completed
    ok = client.post(
        "/api/v1/workflow/resume",
        headers=headers,
        json={
            "case_id": target_case,
            "decision": "reject",
            "note": "Manual outreach already completed by phone.",
        },
    )
    assert ok.status_code == 200
    assert ok.json()["status"] == "completed"
