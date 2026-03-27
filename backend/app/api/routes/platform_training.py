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
