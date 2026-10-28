# Decisions log

Conservative defaults chosen where the spec is ambiguous or conflicts with the environment. One line each.

| # | Milestone | Decision | Reason |
|---|-----------|----------|--------|
| 1 | M0 | The workspace root `d:\Careloop-AI` is the `careloop/` repo root. | Keeps a single git repo at the workspace root; the tree inside matches the spec exactly. |
| 2 | M0 | `requires-python = ">=3.11,<3.13"`; local dev uses the owner's Python 3.12, Docker/CI use 3.11. | Owner asked to use the installed 3.12 interpreter; the spec's 3.11 is kept for the shipped image and CI. |
| 3 | M0 | Python commands run from `apps/api` (e.g. `cd apps/api; uv run pytest tests -q`) or with `uv run --project apps/api`. | `uv.lock` must live in `apps/api` per the tree; a root uv workspace would move the lock file. |
| 4 | M0 | `/healthz` (and later `/healthz/db`) are mounted at the root, not under `/api/v1`. | Spec lists them separately from base-path routes; HF and cron probes expect a short path. |
| 5 | M0 | Unhandled exceptions return 500 with the standard envelope (`internal_error`). | Spec code list omits 500, but a raw stack trace must never reach the client. |
| 6 | M0 | Frontend uses a system font stack instead of `next/font/google`. | Avoids a network fetch at build time and supports Devanagari via local fonts. |
| 7 | M0 | Request-ID middleware is pure ASGI and lives in `core/logging.py`. | The tree has no middleware module; pure ASGI keeps SSE streaming intact. |
| 8 | M3 | Keep M2 data generator untouched and report honest test ROC-AUC (0.6403) alongside the [0.72, 0.90] diagnostic target; fall back to `WeibullAFTFitter` when `proportional_hazard_test` flags `p < 0.01`. | Build instructions explicitly forbid manipulating the data generator or evaluation to force a threshold pass; calibrated ECE (0.0097 <= 0.05) and Brier (0.1848) pass directly. |
