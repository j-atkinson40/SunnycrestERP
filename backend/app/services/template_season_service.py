"""Template season service — date-range visibility rules for quick order templates."""

import uuid
from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from app.models.template_season import TemplateSeason


def _date_in_season(today: date, s: TemplateSeason) -> bool:
    """True if today's month/day falls within the season's date range."""
    md_today = (today.month, today.day)
    md_start = (s.start_month, s.start_day)
    md_end = (s.end_month, s.end_day)

    if md_start <= md_end:
        # Normal range e.g. March 15 → May 31
        return md_start <= md_today <= md_end
    else:
        # Wraps year e.g. Nov 1 → Jan 31
        return md_today >= md_start or md_today <= md_end


def get_active_season(db: Session, company_id: str) -> TemplateSeason | None:
    """Return the first active season whose date range contains today, or None."""
    today = date.today()
    seasons = (
        db.query(TemplateSeason)
        .filter(
            TemplateSeason.company_id == company_id,
            TemplateSeason.is_active.is_(True),
        )
        .all()
    )
    for s in seasons:
        if _date_in_season(today, s):
            return s
    return None


def list_seasons(db: Session, company_id: str) -> list[dict]:
    seasons = (
        db.query(TemplateSeason)
        .filter(TemplateSeason.company_id == company_id)
        .order_by(TemplateSeason.start_month, TemplateSeason.start_day)
        .all()
    )
    return [_to_dict(s) for s in seasons]


def get_season(db: Session, company_id: str, season_id: str) -> TemplateSeason | None:
    return (
        db.query(TemplateSeason)
        .filter(
            TemplateSeason.company_id == company_id,
            TemplateSeason.id == season_id,
        )
        .first()
    )


def create_season(
    db: Session,
    company_id: str,
    season_name: str,
    start_month: int,
    start_day: int,
    end_month: int,
    end_day: int,
    active_template_ids: list | None = None,
) -> dict:
    s = TemplateSeason(
        id=str(uuid.uuid4()),
        company_id=company_id,
        season_name=season_name,
        start_month=start_month,
        start_day=start_day,
        end_month=end_month,
        end_day=end_day,
        active_template_ids=active_template_ids or [],
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return _to_dict(s)


def update_season(db: Session, company_id: str, season_id: str, **fields) -> dict | None:
    s = get_season(db, company_id, season_id)
    if not s:
        return None
    for k, v in fields.items():
        if hasattr(s, k):
            setattr(s, k, v)
    db.commit()
    db.refresh(s)
    return _to_dict(s)


def delete_season(db: Session, company_id: str, season_id: str) -> bool:
    s = get_season(db, company_id, season_id)
    if not s:
        return False
    db.delete(s)
    db.commit()
    return True


def _to_dict(s: TemplateSeason) -> dict:
    return {
        "id": s.id,
        "company_id": s.company_id,
        "season_name": s.season_name,
        "start_month": s.start_month,
        "start_day": s.start_day,
        "end_month": s.end_month,
        "end_day": s.end_day,
        "active_template_ids": list(s.active_template_ids or []),
        "is_active": s.is_active,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }
