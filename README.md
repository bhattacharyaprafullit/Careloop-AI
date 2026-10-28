# CareLoop AI — Closing the Screening-to-Care Loop

> **Demo only, synthetic data.** Decision support only — CareLoop AI never diagnoses, prescribes or makes autonomous clinical decisions. Synthetic-data model performance is **not** evidence of real-world clinical effectiveness.

**Live demo:** _<placeholder — added after deployment>_

CareLoop AI makes sure every actionable screening result (FIT, mammography, Pap/HPV) is communicated, confirmed and converted into timely care, with a clear owner, an SLA at every step, human-governed escalation and documented closure.

## Status

| Milestone | Title | Status |
|-----------|-------|--------|
| M0 | Scaffold | done |
| M1–M11 | see spec | pending |

## Repository layout

```
apps/api   FastAPI backend (domain rules, DB, ML inference, LLM, LangGraph)
apps/web   Next.js frontend (App Router, TypeScript strict, Tailwind)
ml/        synthetic data generator, training and evaluation scripts, artifacts
docs/      model card, data card, traceability, architecture
```

## Local development

Prerequisites: Python 3.11 or 3.12, [uv](https://docs.astral.sh/uv/), Node.js 20+.

```powershell
# Backend
cd apps/api
uv sync
uv run pytest tests -q
uv run uvicorn app.main:app --reload --port 7860   # http://localhost:7860/healthz

# Frontend (second terminal)
cd apps/web
npm install
npm run dev                                         # http://localhost:3000
```

Copy `.env.example` to `.env` and adjust. No secrets are needed for local demo mode.

## Demo path, requirement-to-feature table and limitations

Filled in at M10/M11.
