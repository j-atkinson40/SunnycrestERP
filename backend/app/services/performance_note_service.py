from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.performance_note import PerformanceNote
from app.schemas.performance_note import PerformanceNoteCreate


def get_notes_for_user(
    db: Session, user_id: str, company_id: str
) -> list[PerformanceNote]:
    return (
        db.query(PerformanceNote)
        .filter(
            PerformanceNote.user_id == user_id,
            PerformanceNote.company_id == company_id,
        )
        .order_by(PerformanceNote.created_at.desc())
        .all()
    )


def create_note(
    db: Session,
    data: PerformanceNoteCreate,
    company_id: str,
    author_id: str,
) -> PerformanceNote:
    valid_types = {"review", "note", "goal", "warning"}
    if data.type not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid note type. Must be one of: {', '.join(valid_types)}",
        )

    note = PerformanceNote(
        company_id=company_id,
        user_id=data.user_id,
        author_id=author_id,
        type=data.type,
        title=data.title,
        content=data.content,
        review_date=data.review_date,
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return note


def delete_note(
    db: Session, note_id: str, company_id: str
) -> None:
    note = (
        db.query(PerformanceNote)
        .filter(
            PerformanceNote.id == note_id,
            PerformanceNote.company_id == company_id,
        )
        .first()
    )
    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Performance note not found",
        )
    db.delete(note)
    db.commit()
