from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.database import get_db
from app.models.user import User
from app.schemas.performance_note import (
    PerformanceNoteCreate,
    PerformanceNoteResponse,
)
from app.services.performance_note_service import (
    create_note,
    delete_note,
    get_notes_for_user,
)

router = APIRouter()


@router.get("", response_model=list[PerformanceNoteResponse])
def list_notes(
    user_id: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("employees.view_notes")),
):
    return get_notes_for_user(db, user_id, current_user.company_id)


@router.post("", status_code=201, response_model=PerformanceNoteResponse)
def create(
    data: PerformanceNoteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("employees.edit")),
):
    return create_note(
        db, data, current_user.company_id, author_id=current_user.id
    )


@router.delete("/{note_id}")
def remove(
    note_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("employees.edit")),
):
    delete_note(db, note_id, current_user.company_id)
    return {"detail": "Performance note deleted"}
