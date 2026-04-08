"""Public intake form API endpoints — no auth, token-validated.

These endpoints are used by the public-facing disinterment intake form
that funeral directors fill out on their phones.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.disinterment import IntakeFormData, IntakeSubmitResponse, IntakeTokenResponse
from app.services import disinterment_service

router = APIRouter()


@router.get("/{token}")
def validate_intake_token(
    token: str,
    db: Session = Depends(get_db),
):
    """Public — validate an intake token and return case info.

    No authentication required. Returns whether the form has
    already been submitted.
    """
    return disinterment_service.validate_intake_token(db, token)


@router.post("/{token}")
def submit_intake_form(
    token: str,
    data: IntakeFormData,
    db: Session = Depends(get_db),
):
    """Public — submit the intake form. Token is single-use.

    Once submitted, the token cannot be reused. Staff reviews
    the submission via the case detail page.
    """
    result = disinterment_service.submit_intake(db, token, data)
    return IntakeSubmitResponse(
        case_number=result["case_number"],
    )
