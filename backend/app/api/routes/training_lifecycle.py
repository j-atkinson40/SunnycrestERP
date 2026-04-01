"""Training lifecycle progress tracking endpoints."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.training_progress import TrainingProgress
from app.models.user import User

router = APIRouter()

VAULT_LIFECYCLE_KEY = "vault_order_lifecycle"
VAULT_LIFECYCLE_STAGES = [
    "entry", "scheduling", "invoicing", "billing", "collections", "payment", "completion"
]


@router.get("/vault-order-lifecycle/progress")
def get_vault_lifecycle_progress(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the current user's progress on the vault order lifecycle training."""
    records = (
        db.query(TrainingProgress)
        .filter(
            TrainingProgress.user_id == current_user.id,
            TrainingProgress.training_key == VAULT_LIFECYCLE_KEY,
        )
        .all()
    )

    completed_stages = [r.stage_key for r in records]
    all_complete = set(VAULT_LIFECYCLE_STAGES).issubset(set(completed_stages))

    # Find the latest completion time
    completed_at = None
    if all_complete and records:
        completed_at = max(r.completed_at for r in records).isoformat()

    return {
        "stages_completed": completed_stages,
        "total_stages": len(VAULT_LIFECYCLE_STAGES),
        "all_complete": all_complete,
        "completed_at": completed_at,
    }


@router.post("/vault-order-lifecycle/stages/{stage_key}/complete")
def complete_vault_lifecycle_stage(
    stage_key: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark a vault lifecycle stage as complete for the current user."""
    if stage_key not in VAULT_LIFECYCLE_STAGES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid stage key. Must be one of: {', '.join(VAULT_LIFECYCLE_STAGES)}",
        )

    # Upsert — don't error on duplicate
    existing = (
        db.query(TrainingProgress)
        .filter(
            TrainingProgress.user_id == current_user.id,
            TrainingProgress.training_key == VAULT_LIFECYCLE_KEY,
            TrainingProgress.stage_key == stage_key,
        )
        .first()
    )
    if not existing:
        record = TrainingProgress(
            id=str(uuid.uuid4()),
            company_id=current_user.company_id,
            user_id=current_user.id,
            training_key=VAULT_LIFECYCLE_KEY,
            stage_key=stage_key,
        )
        db.add(record)
        db.commit()

    # Check overall progress
    completed_count = (
        db.query(TrainingProgress)
        .filter(
            TrainingProgress.user_id == current_user.id,
            TrainingProgress.training_key == VAULT_LIFECYCLE_KEY,
        )
        .count()
    )

    all_complete = completed_count >= len(VAULT_LIFECYCLE_STAGES)

    # Fire onboarding hook if all complete
    if all_complete:
        try:
            from app.services.onboarding_hooks import on_training_lifecycle_completed

            on_training_lifecycle_completed(db, current_user.company_id)
        except Exception:
            pass

    return {
        "stages_completed": completed_count,
        "total_stages": len(VAULT_LIFECYCLE_STAGES),
        "all_complete": all_complete,
    }
