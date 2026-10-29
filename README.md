# CareLoop AI — Closing the Screening-to-Care Loop

> **Demo Only — 100% Synthetic Data:** CareLoop AI is a clinical coordination decision-support platform built for the **"Closing the Screening-to-Care Loop"** challenge. It uses exclusively synthetic patient records and never diagnoses conditions, never prescribes medications, and never closes cases autonomously.

---

## Overview (Requirements R1–R6)
CareLoop AI ensures that every actionable cancer screening result (`FIT`, `MAMMOGRAPHY`, `PAP_HPV`) is communicated, confirmed, and converted into timely care with a clear owner, explicit SLA deadline, explainable ML risk scoring, and documented evidence before closure:

- **R1 — End-to-End 11-State Lifecycle Visibility:** `RESULT_ISSUED` → `PATIENT_NOTIFIED` → `ACKNOWLEDGED` → `CONFIRMATORY_PENDING` → `REFERRAL_SENT` → `REJECTED` / `REFERRAL_ACCEPTED` → `APPOINTMENT_BOOKED` → `SEEN` → `TREATMENT_OR_SURVEILLANCE` → `CLOSED`, backed by an immutable append-only event ledger (`case_events`).
- **R2 — Clear Ownership & SLA Clocks:** Every state assigns a responsible owner role (`coordinator` or `clinician`) and SLA hours (urgent Tier 1 halves SLA hours). Coordinators filter by `Overdue`, `Unassigned`, `Rejected`, and `Needs approval`.
- **R3 — Multilingual Patient Communication & Teach-Back:** Patient portal (`/p/[token]`) in English (`en`), Hindi (`hi`), and Spanish (`es`) with automatic English fallback, 3-step progress tracker, **I understand** acknowledgement, and teach-back comprehension verification (`understood`, `partial`, `confused`).
- **R4 — Cross-Provider SBAR Referrals & Consultations:** Fact-validated SBAR referral hand-offs, specialist accept/reject with structured `ReasonCode` (rejection automatically re-queues to the coordinator), and `patient_to_clinician` / `clinician_to_clinician` consult threads.
- **R5 — Human-Governed Escalation & Closure Gate:** High-risk (`p_dropoff > 0.65`), urgent overdue, confused teach-back, rejected referral, or high-divergence (`ADS > 0.50`) cases pause at a checkpointed LangGraph `interrupt()` gate until a human approves, modifies, or rejects. Closing a case requires allowed closure evidence (`treatment_started`, `surveillance_plan`, `benign_confirmed`, `patient_declined_counseled`) or an authorized clinician override with a documented reason.
- **R6 — Loop-Closure Metrics & Queue Simulation:** Real-time stage transition medians/P90s, referral/appointment completion rates, unresolved aging buckets, delay reasons, documented closure rate, teach-back understanding rate, and a 100-run Monte Carlo simulation comparing FIFO outreach (`36.50d` median closure) vs. CareLoop priority queue (`33.67d` median closure).

---

## Quick Start (Local Development — Zero API Keys Required)

### 1. Start the FastAPI Backend (`http://localhost:7860`)
```powershell
cd d:\Careloop-AI\apps\api
uv run alembic upgrade head
uv run uvicorn app.main:app --host 127.0.0.1 --port 7860 --reload
```

### 2. Start the Next.js Frontend (`http://localhost:3000`)
```powershell
cd d:\Careloop-AI\apps\web
npm run dev
```
Open **http://localhost:3000** and click **Launch live demo** to provision an isolated 60-case sandbox and start the 8-step Guided Tour.

---

## Running Tests & Evaluations

### Backend Unit & Integration Tests (`pytest`, `ruff`, `mypy`)
```powershell
cd d:\Careloop-AI\apps\api
uv run ruff check .
uv run mypy app
uv run pytest -q
```

### Frontend Lint, Typecheck, Build & Playwright E2E Tests
```powershell
cd d:\Careloop-AI\apps\web
npm run lint
npm run typecheck
npm run build
npx playwright test
```

### Re-running Synthetic Data Generation, ML Training & M11 Audits
```powershell
$env:PYTHONPATH="d:\Careloop-AI;d:\Careloop-AI\apps\api"
cd d:\Careloop-AI\apps\api
uv run python -m ml.data.generate
uv run python -m ml.train.evaluate
uv run python -m ml.eval.fairness
uv run python -m ml.eval.shap_stability
uv run python -m ml.eval.llm_faithfulness
uv run python -m ml.eval.simulate_queue
```

---

## Documentation Index
- [`docs/architecture.md`](docs/architecture.md) — System architecture, domain invariants, and official references consulted.
- [`docs/model-card.md`](docs/model-card.md) — Honest test-split metrics, calibration ECE/Brier, WeibullAFT survival C-index, 20-bootstrap SHAP stability, subgroup fairness, and limitations.
- [`docs/data-card.md`](docs/data-card.md) — 12,000-patient synthetic cohort schema, coefficients, stage rates, and leakage checks.
- [`docs/TRACEABILITY.md`](docs/TRACEABILITY.md) — End-to-end R1–R6 traceability across domain, API, UI, and tests.
- [`DEPLOY_CHECKLIST.md`](DEPLOY_CHECKLIST.md) — Step-by-step ₹0 free-tier deployment guide (Supabase, Hugging Face Docker Space, Vercel, Groq, GitHub Actions).
- [`DECISIONS.md`](DECISIONS.md) — Conservative engineering decisions logged during implementation.
