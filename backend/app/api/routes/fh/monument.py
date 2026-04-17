"""Monument catalog endpoints — shapes, stones, engravings, accessories + AI suggestion."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.data import monument_catalog
from app.database import get_db
from app.models.funeral_case import CaseDeceased, CaseVeteran
from app.models.user import User


router = APIRouter()


@router.get("/shapes")
def shapes(current_user: User = Depends(get_current_user)):
    return monument_catalog.get_shapes()


@router.get("/stones")
def stones(current_user: User = Depends(get_current_user)):
    return monument_catalog.get_stones()


@router.get("/engravings")
def engravings(
    category: str | None = None,
    current_user: User = Depends(get_current_user),
):
    return monument_catalog.get_engravings(category)


@router.get("/accessories/{shape}")
def accessories_for_shape(
    shape: str,
    current_user: User = Depends(get_current_user),
):
    return monument_catalog.get_accessories_for_shape(shape)


@router.get("/suggest/{case_id}")
def suggest_engraving_for_case(
    case_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    dec = db.query(CaseDeceased).filter(
        CaseDeceased.case_id == case_id,
        CaseDeceased.company_id == current_user.company_id,
    ).first()
    vet = db.query(CaseVeteran).filter(
        CaseVeteran.case_id == case_id,
        CaseVeteran.company_id == current_user.company_id,
    ).first()

    suggestion = monument_catalog.suggest_engraving(
        is_veteran=bool(vet and vet.ever_in_armed_forces),
        branch=vet.branch if vet else None,
        religion=dec.religion if dec else None,
    )
    return {
        "suggestion": suggestion,
        "engraving": monument_catalog.ENGRAVINGS.get(suggestion),
    }
