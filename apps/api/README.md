---
title: CareLoop AI API
emoji: 🩺
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: false
---

# CareLoop AI — API

FastAPI backend for CareLoop AI. **Demo only, synthetic data. Decision support only — no diagnosis, no prescribing.**

Local development (from `apps/api`):

```powershell
uv sync
uv run uvicorn app.main:app --reload --port 7860
uv run pytest -q
```

See the repository root `README.md` for the full project description.
