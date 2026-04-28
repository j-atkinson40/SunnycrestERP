"""Operator profile API — Phase W-4a operator onboarding endpoints.

Surfaces the user's work_areas + responsibilities_description per
BRIDGEABLE_MASTER §3.26.3. User-scoped via `get_current_user` —
every user manages their own profile; no admin override path here
(admin user management lives at `/api/v1/users/*` for tenant-scope
operations like creation/deletion).

Endpoints:
  GET   /api/v1/operator-profile  — read current profile state
  PATCH /api/v1/operator-profile  — partial update (auto-save friendly)

The PATCH endpoint supports both auto-save (each Textarea keystroke
debounce-flushed sends `responsibilities_description`) and explicit
finalize (frontend Save-and-continue button sends
`mark_onboarding_complete: true`).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.services.operator_profile_service import (
    OperatorProfileError,
    RESPONSIBILITIES_MAX_LENGTH,
    WORK_AREAS,
    get_operator_profile,
    update_operator_profile,
)


router = APIRouter()


class _OperatorProfileResponse(BaseModel):
    work_areas: list[str]
    responsibilities_description: str | None
    onboarding_completed: bool
    available_work_areas: list[str]


class _OperatorProfileUpdateRequest(BaseModel):
    """Partial-update body. All fields optional — Pydantic
    `model_fields_set` distinguishes "field omitted" from "field set
    to null" so we can correctly leave-untouched-vs-clear."""

    work_areas: list[str] | None = None
    responsibilities_description: str | None = Field(
        default=None,
        max_length=RESPONSIBILITIES_MAX_LENGTH,
    )
    mark_onboarding_complete: bool = False


@router.get("", response_model=_OperatorProfileResponse)
def read_operator_profile(
    current_user: User = Depends(get_current_user),
):
    """Return current user's operator profile.

    `available_work_areas` is the canonical work-area vocabulary; the
    frontend renders multi-select cards from this list.
    """
    return get_operator_profile(current_user)


@router.patch("", response_model=_OperatorProfileResponse)
def patch_operator_profile(
    body: _OperatorProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update current user's operator profile.

    Partial-update semantics: only fields explicitly set in the body
    are modified. Pass `work_areas=null` or `[]` to clear; omit the
    key to leave untouched. Same pattern for
    `responsibilities_description`.

    `mark_onboarding_complete=true` writes the
    `preferences.onboarding_touches.operator_profile` flag so the
    first-login redirect logic stops triggering.
    """
    fields_set = body.model_fields_set
    # Build kwargs only for fields that are explicitly set so the
    # service's "None = leave untouched" semantics don't swallow
    # explicit clears (frontend sends `work_areas: []` to clear; that
    # IS in fields_set, value is `[]`, service correctly clears via
    # _validate_work_areas).
    kwargs: dict = {
        "mark_onboarding_complete": body.mark_onboarding_complete,
    }
    if "work_areas" in fields_set:
        # Explicit clear via empty list; explicit null becomes empty
        # list so the service uniformly treats both as "clear".
        kwargs["work_areas"] = body.work_areas if body.work_areas is not None else []
    if "responsibilities_description" in fields_set:
        # Explicit null clears; empty string also normalizes to null
        # in the service via _validate_responsibilities.
        kwargs["responsibilities_description"] = (
            body.responsibilities_description
            if body.responsibilities_description is not None
            else ""
        )
    try:
        return update_operator_profile(db, user=current_user, **kwargs)
    except OperatorProfileError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


# Re-exported for tests that want to assert the canonical work-area
# vocabulary. Importing from the route module is the canonical path
# because the API surface is the contract the frontend depends on.
__all__ = ["router", "WORK_AREAS"]
