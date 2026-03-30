"""Platform admin routes for training content generation."""

import json
import logging

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import require_platform_role
from app.database import get_db
from app.models.platform_user import PlatformUser

logger = logging.getLogger(__name__)
router = APIRouter()


class GenerateContentRequest(BaseModel):
    force: bool = False  # If True, regenerate even if content already exists


class RegenerateProceduresRequest(BaseModel):
    keys: list[str]  # Specific procedure keys to regenerate


@router.get("/content-status")
def get_content_status(
    _user: PlatformUser = Depends(require_platform_role("super_admin", "support", "viewer")),
    db: Session = Depends(get_db),
):
    """Check whether shared training content has been generated."""
    from app.services.training_content_generation_service import get_content_status
    return get_content_status(db)


@router.post("/generate-content")
def generate_content(
    body: GenerateContentRequest = GenerateContentRequest(),
    _user: PlatformUser = Depends(require_platform_role("super_admin")),
    db: Session = Depends(get_db),
):
    """Generate shared training procedures and curriculum tracks via Claude API.

    Returns a streaming newline-delimited JSON response so the caller can
    display live progress as each item is generated.
    """
    from app.services.training_content_generation_service import generate_all_content

    def event_stream():
        try:
            for event in generate_all_content(db, force=body.force):
                yield json.dumps(event) + "\n"
        except Exception as e:
            logger.error("Training content generation failed: %s", e)
            yield json.dumps({"type": "error", "message": str(e)}) + "\n"

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")


@router.post("/regenerate-procedures")
def regenerate_procedures(
    body: RegenerateProceduresRequest,
    _user: PlatformUser = Depends(require_platform_role("super_admin")),
    db: Session = Depends(get_db),
):
    """Force-regenerate specific procedure keys via Claude API.

    Useful for refreshing procedures after a workflow change without regenerating all content.
    Returns a streaming newline-delimited JSON response.
    """
    from app.services.training_content_generation_service import regenerate_specific_procedures

    def event_stream():
        try:
            for event in regenerate_specific_procedures(db, body.keys):
                yield json.dumps(event) + "\n"
        except Exception as e:
            logger.error("Procedure regeneration failed: %s", e)
            yield json.dumps({"type": "error", "message": str(e)}) + "\n"

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")


@router.post("/patch-curriculum-modules")
def patch_curriculum_modules(
    _user: PlatformUser = Depends(require_platform_role("super_admin")),
    db: Session = Depends(get_db),
):
    """Patch the accounting curriculum track to reference the Invoice Review Queue.

    Updates invoice-related module guided_task platform_action paths to point to
    /ar/invoices/review. Safe to run multiple times (idempotent).
    """
    from app.services.training_content_generation_service import patch_accounting_invoice_modules
    return patch_accounting_invoice_modules(db)
