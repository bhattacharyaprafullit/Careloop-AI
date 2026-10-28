"""FastAPI application factory for CareLoop AI."""
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from app.core.config import get_settings
from app.core.errors import error_response, register_error_handlers
from app.core.logging import REQUEST_ID_HEADER, RequestIdMiddleware, configure_logging
from app.db.session import init_db
from app.routers import (
    cases,
    consults,
    demo,
    health,
    internal,
    metrics,
    patient,
    referrals,
    sandbox,
    screenings,
    workflow,
)
from app.services.inference import load_models

logger = logging.getLogger(__name__)

API_PREFIX = "/api/v1"
limiter = Limiter(key_func=get_remote_address, default_limits=["600/minute"])


async def _rate_limit_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RateLimitExceeded)
    return error_response(429, "rate_limited", "Rate limit exceeded. Please slow down.")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Startup/shutdown hooks: initialize DB tables/triggers and load ML artifacts once."""
    settings = get_settings()
    logger.info("startup", extra={"demo_mode": settings.demo_mode})
    init_db()
    load_models(settings.model_dir)
    yield
    logger.info("shutdown")


def create_app() -> FastAPI:
    """Build the FastAPI app with logging, CORS, rate limits, request IDs and error envelopes."""
    settings = get_settings()
    configure_logging(settings.log_level)
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Decision support only. Synthetic data. No diagnosis, no prescribing.",
        lifespan=lifespan,
    )
    app.state.limiter = limiter
    app.add_middleware(SlowAPIMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=[
            "Content-Type",
            "X-Sandbox-Token",
            "X-Role",
            "X-Cron-Token",
            REQUEST_ID_HEADER,
        ],
        expose_headers=[REQUEST_ID_HEADER],
    )
    app.add_middleware(RequestIdMiddleware)
    register_error_handlers(app)
    app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)

    app.include_router(health.router)
    app.include_router(sandbox.router, prefix=API_PREFIX)
    app.include_router(cases.router, prefix=API_PREFIX)
    app.include_router(screenings.router, prefix=API_PREFIX)
    app.include_router(workflow.router, prefix=API_PREFIX)
    app.include_router(patient.router, prefix=API_PREFIX)
    app.include_router(referrals.router, prefix=API_PREFIX)
    app.include_router(consults.router, prefix=API_PREFIX)
    app.include_router(metrics.router, prefix=API_PREFIX)
    app.include_router(demo.router, prefix=API_PREFIX)
    app.include_router(internal.router, prefix=API_PREFIX)
    return app


app = create_app()
