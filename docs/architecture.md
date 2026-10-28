# Architecture

_Filled in progressively; complete by M11._

## Components (M0)

- **apps/api** — FastAPI app factory (`app/main.py`), pydantic-settings config, JSON logs, pure-ASGI request-ID middleware, uniform error envelope `{error:{code,message,request_id}}`, `/healthz`.
- **apps/web** — Next.js 15 (App Router) + React 19, TypeScript strict, Tailwind v4; global demo-only banner.

## Official docs consulted

| Topic | URL | Used for |
|-------|-----|----------|
| FastAPI | https://fastapi.tiangolo.com/ | app factory, lifespan, exception handlers, CORS |
| Starlette middleware | https://www.starlette.io/middleware/ | pure ASGI middleware pattern |
| pydantic-settings | https://docs.pydantic.dev/latest/concepts/pydantic_settings/ | env/.env configuration |
| uv | https://docs.astral.sh/uv/ | project, lock file, dependency groups |
| Next.js | https://nextjs.org/docs/app | App Router scaffold (create-next-app 15) |
| Tailwind CSS v4 | https://tailwindcss.com/docs | `@import "tailwindcss"` + `@theme` |
