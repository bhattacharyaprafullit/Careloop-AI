"""Patient portal routes (/api/v1/patient/{token}, acknowledge, teachback)."""
import logging
from typing import Any

from fastapi import APIRouter

from app.deps import DbSession
from app.schemas.patient import (
    PatientPortalResponse,
    TeachBackRequest,
    TeachBackResponse,
)
from app.services.comms import (
    acknowledge_patient_result,
    get_patient_portal_view,
    submit_patient_teachback,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["patient"])


@router.get("/patient/{token}", response_model=PatientPortalResponse)
def get_patient_page(
    token: str,
    db: DbSession,
    lang: str | None = None,
) -> PatientPortalResponse:
    """Return patient-friendly 3-step tracker, localized message, and due date."""
    return get_patient_portal_view(db, token, lang_override=lang)


@router.post("/patient/{token}/acknowledge")
def post_patient_acknowledge(
    token: str,
    db: DbSession,
) -> dict[str, Any]:
    """Acknowledge receipt of screening result ("I understand" button)."""
    return acknowledge_patient_result(db, token)


@router.post("/patient/{token}/teachback", response_model=TeachBackResponse)
def post_patient_teachback(
    token: str,
    body: TeachBackRequest,
    db: DbSession,
) -> TeachBackResponse:
    """Submit teach-back confirmation text and classify as understood, partial, or confused."""
    return submit_patient_teachback(db, token, body.reply_text)
