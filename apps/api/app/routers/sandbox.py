"""POST /api/v1/sandbox endpoint (M5)."""
import logging

from fastapi import APIRouter, status

from app.deps import DbSession
from app.schemas.common import SandboxResponse
from app.services.sandbox import launch_sandbox

logger = logging.getLogger(__name__)

router = APIRouter(tags=["sandbox"])


@router.post("/sandbox", response_model=SandboxResponse, status_code=status.HTTP_201_CREATED)
def create_sandbox(db: DbSession) -> SandboxResponse:
    """Clone the 60 seed cases and pre-generated LLM outputs into an isolated 24-hour sandbox."""
    return launch_sandbox(db)
