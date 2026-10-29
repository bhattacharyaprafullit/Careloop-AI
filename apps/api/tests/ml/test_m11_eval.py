"""M11 evaluation & failure-drill tests: fairness, SHAP stability, LLM faithfulness, and docs."""
import logging
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from ml.eval.fairness import evaluate_subgroup_fairness
from ml.eval.llm_faithfulness import evaluate_llm_faithfulness
from ml.eval.shap_stability import evaluate_shap_stability
from sqlalchemy.exc import OperationalError

from app.db.session import get_session
from app.domain.states import LLMKind
from app.llm.client import generate_validated_llm_output
from app.main import create_app

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[4]


def test_m11_subgroup_fairness_and_shap_stability() -> None:
    """Verify subgroup fairness and 20-bootstrap SHAP stability run and meet stability targets."""
    fairness = evaluate_subgroup_fairness()
    assert "dimensions" in fairness
    for dim in (
        "age_bracket",
        "insurance_category",
        "preferred_language",
        "distance_band",
        "screening_type",
    ):
        assert dim in fairness["dimensions"]

    stability = evaluate_shap_stability(bootstrap_runs=20, sample_size=500, seed=42)
    assert stability["bootstrap_runs"] == 20
    assert stability["mean_spearman_rho"] >= 0.85
    assert stability["top3_overlap_rate"] >= 0.80


def test_m11_llm_faithfulness_200_cases() -> None:
    """Verify 200-case LLM faithfulness audit achieves 100% validator pass rate and low ADS."""
    res = evaluate_llm_faithfulness(n_cases=200)
    assert res["evaluated_cases"] == 200
    assert res["validator_pass_rate"] == 1.0
    assert res["mean_ads"] <= 0.50


def test_m11_failure_drills_no_groq_key_and_db_down() -> None:
    """Drill 1: No Groq key falls back cleanly to template. Drill 2: DB down returns 503."""
    # Drill 1: No Groq key -> deterministic template with source='template'
    facts: dict[str, Any] = {
        "state": "RESULT_ISSUED",
        "owner_role": "clinician",
        "days_in_state": 1,
        "sla_hours_remaining": 24,
        "p_dropoff_percent": 32,
        "shap_top_positive": [{"feature": "prior_noshow_ratio", "value": 0.25}],
    }
    res = generate_validated_llm_output(LLMKind.CASE_SUMMARY.value, facts)
    assert res["source"] == "template"
    assert res["faithful_ok"] is True

    # Drill 2: Database unavailable on /healthz/db -> returns 503 db_unavailable
    app = create_app()

    def _broken_db() -> Any:
        class _BrokenSession:
            def execute(self, *_args: Any, **_kwargs: Any) -> Any:
                raise OperationalError("SELECT 1", {}, Exception("simulated db down"))

        yield _BrokenSession()

    app.dependency_overrides[get_session] = _broken_db
    client = TestClient(app)
    resp = client.get("/healthz/db")
    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "db_unavailable"


def test_m11_required_docs_and_workflows_exist() -> None:
    """Verify all required M11 documentation files and GitHub workflows exist and are non-empty."""
    required_paths = [
        REPO_ROOT / "README.md",
        REPO_ROOT / "DECISIONS.md",
        REPO_ROOT / "DEPLOY_CHECKLIST.md",
        REPO_ROOT / ".env.example",
        REPO_ROOT / "docs" / "model-card.md",
        REPO_ROOT / "docs" / "data-card.md",
        REPO_ROOT / "docs" / "architecture.md",
        REPO_ROOT / "docs" / "TRACEABILITY.md",
        REPO_ROOT / ".github" / "workflows" / "ci.yml",
        REPO_ROOT / ".github" / "workflows" / "keepalive.yml",
        REPO_ROOT / "apps" / "api" / "Dockerfile",
        REPO_ROOT / "apps" / "web" / "vercel.json",
    ]
    for p in required_paths:
        assert p.exists(), f"Missing required file: {p}"
        assert p.stat().st_size > 100, f"File unexpectedly empty: {p}"
