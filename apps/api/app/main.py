"""FastAPI application factory for CareLoop AI."""
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.core.logging import REQUEST_ID_HEADER, RequestIdMiddleware, configure_logging
from app.db.session import init_db
from app.routers import cases, health, sandbox, screenings, workflow
from app.services.inference import load_models

logger = logging.getLogger(__name__)

API_PREFIX = "/api/v1"


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
    """Build the FastAPI app with logging, CORS, request IDs and error envelopes."""
    settings = get_settings()
    configure_logging(settings.log_level)
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Decision support only. Synthetic data. No diagnosis, no prescribing.",
        lifespan=lifespan,
    )
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
    app.include_router(health.router)
    app.include_router(sandbox.router, prefix=API_PREFIX)
    app.include_router(cases.router, prefix=API_PREFIX)
    app.include_router(screenings.router, prefix=API_PREFIX)
    app.include_router(workflow.router, prefix=API_PREFIX)
    return app


app = create_app()
