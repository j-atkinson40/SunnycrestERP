"""Template season routes — seasonal visibility rules for quick order templates."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User

router = APIRouter()


class SeasonCreate(BaseModel):
    season_name: str
    start_month: int
    start_day: int
    end_month: int
    end_day: int
    active_template_ids: list[str] = []


class SeasonUpdate(BaseModel):
    season_name: str | None = None
    start_month: int | None = None
    start_day: int | None = None
    end_month: int | None = None
    end_day: int | None = None
    active_template_ids: list[str] | None = None
    is_active: bool | None = None


@router.get("/")
def list_seasons(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.services.template_season_service import list_seasons as svc_list
    return svc_list(db, current_user.company_id)


@router.post("/", status_code=201)
def create_season(
    body: SeasonCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.services.template_season_service import create_season as svc_create
    return svc_create(db, current_user.company_id, **body.model_dump())


@router.patch("/{season_id}")
def update_season(
    season_id: str,
    body: SeasonUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.services.template_season_service import update_season as svc_update
    result = svc_update(
        db, current_user.company_id, season_id, **body.model_dump(exclude_none=True)
    )
    if not result:
        raise HTTPException(status_code=404, detail="Season not found")
    return result


@router.delete("/{season_id}", status_code=204)
def delete_season(
    season_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.services.template_season_service import delete_season as svc_delete
    if not svc_delete(db, current_user.company_id, season_id):
        raise HTTPException(status_code=404, detail="Season not found")
