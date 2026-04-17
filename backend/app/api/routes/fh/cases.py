"""Funeral home case management endpoints.

All endpoints require a tenant user and scope to company_id. Hybrid tenancy:
these endpoints work for any tenant today (funeral_home or manufacturer) —
a manufacturer with the FH models won't be blocked. A hard tenant-type check
can be added later once the tenant_type column is populated consistently.
"""

from datetime import date, datetime, time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.funeral_case import (
    CaseDeceased,
    CaseDisposition,
    CaseInformant,
    CaseMerchandise,
    CaseService,
    CaseVeteran,
    FuneralCase,
    FuneralCaseNote,
)
from app.models.user import User
from app.services.fh import case_service, scribe_service, story_thread_service
from app.services.fh import crypto


router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────────────────────────────────────

class CreateCaseRequest(BaseModel):
    location_id: Optional[str] = None
    director_id: Optional[str] = None


class CaseListQuery(BaseModel):
    status: Optional[str] = None
    director_id: Optional[str] = None
    location_id: Optional[str] = None
    search: Optional[str] = None


class UpdateDeceasedRequest(BaseModel):
    first_name: Optional[str] = None
    middle_name: Optional[str] = None
    last_name: Optional[str] = None
    suffix: Optional[str] = None
    maiden_name: Optional[str] = None
    date_of_birth: Optional[date] = None
    date_of_death: Optional[date] = None
    time_of_death: Optional[time] = None
    sex: Optional[str] = None
    religion: Optional[str] = None
    occupation: Optional[str] = None
    marital_status: Optional[str] = None
    ssn: Optional[str] = None   # plaintext — encrypted on write
    place_of_death_name: Optional[str] = None
    place_of_death_city: Optional[str] = None
    place_of_death_state: Optional[str] = None
    residence_city: Optional[str] = None
    residence_state: Optional[str] = None
    residence_county: Optional[str] = None
    father_name: Optional[str] = None
    mother_maiden_name: Optional[str] = None
    spouse_name: Optional[str] = None


class UpdateServiceRequest(BaseModel):
    service_type: Optional[str] = None
    service_date: Optional[date] = None
    service_time: Optional[time] = None
    service_location_name: Optional[str] = None
    service_location_address: Optional[str] = None
    officiant_name: Optional[str] = None
    officiant_phone: Optional[str] = None
    visitation_date: Optional[date] = None
    visitation_start_time: Optional[time] = None
    visitation_end_time: Optional[time] = None
    visitation_location: Optional[str] = None
    pallbearers: Optional[list[str]] = None
    special_instructions: Optional[str] = None
    obituary_draft: Optional[str] = None
    obituary_final: Optional[str] = None


class AddInformantRequest(BaseModel):
    name: str
    relationship: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    is_primary: bool = False
    is_authorizing: bool = False


class AddNoteRequest(BaseModel):
    content: str
    note_type: str = "general"


class ScribeProcessRequest(BaseModel):
    transcript: str


class AdvanceStepRequest(BaseModel):
    step_key: str


# ─────────────────────────────────────────────────────────────────────────
# Case CRUD
# ─────────────────────────────────────────────────────────────────────────

@router.post("")
def create_case(
    data: CreateCaseRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    case = case_service.create_case(
        db=db,
        company_id=current_user.company_id,
        director_id=data.director_id or current_user.id,
        location_id=data.location_id,
    )
    return {
        "id": case.id,
        "case_number": case.case_number,
        "status": case.status,
        "current_step": case.current_step,
    }


@router.get("")
def list_cases(
    status: Optional[str] = Query(None),
    director_id: Optional[str] = Query(None),
    location_id: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(FuneralCase).filter(FuneralCase.company_id == current_user.company_id)
    if status:
        q = q.filter(FuneralCase.status == status)
    if director_id:
        q = q.filter(FuneralCase.director_id == director_id)
    if location_id:
        q = q.filter(FuneralCase.location_id == location_id)

    cases = q.order_by(FuneralCase.opened_at.desc()).limit(200).all()
    out = []
    for case in cases:
        dec = db.query(CaseDeceased).filter(CaseDeceased.case_id == case.id).first()
        name = " ".join([p for p in [dec.first_name if dec else None, dec.last_name if dec else None] if p])
        if search and search.lower() not in name.lower() and search.lower() not in case.case_number.lower():
            continue
        out.append({
            "id": case.id,
            "case_number": case.case_number,
            "deceased_name": name or case.case_number,
            "status": case.status,
            "current_step": case.current_step,
            "director_id": case.director_id,
            "location_id": case.location_id,
            "opened_at": case.opened_at.isoformat() if case.opened_at else None,
        })
    return out


@router.get("/{case_id}")
def get_case(
    case_id: str,
    include_ssn: bool = Query(False, description="If true, decrypt and return SSN plaintext."),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    case = db.query(FuneralCase).filter(
        FuneralCase.id == case_id,
        FuneralCase.company_id == current_user.company_id,
    ).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    try:
        return case_service.get_case_detail(db, case_id, include_ssn=include_ssn)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{case_id}/staircase")
def get_staircase(
    case_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    case = db.query(FuneralCase).filter(
        FuneralCase.id == case_id,
        FuneralCase.company_id == current_user.company_id,
    ).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return case_service.get_staircase(db, case_id)


@router.post("/{case_id}/staircase/advance")
def advance_step(
    case_id: str,
    data: AdvanceStepRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    case = db.query(FuneralCase).filter(
        FuneralCase.id == case_id,
        FuneralCase.company_id == current_user.company_id,
    ).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    case = case_service.advance_step(db, case_id, data.step_key)
    return {"case_id": case.id, "current_step": case.current_step, "status": case.status}


# ─────────────────────────────────────────────────────────────────────────
# Deceased + Service + Informants
# ─────────────────────────────────────────────────────────────────────────

@router.patch("/{case_id}/deceased")
def update_deceased(
    case_id: str,
    data: UpdateDeceasedRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    case = db.query(FuneralCase).filter(
        FuneralCase.id == case_id,
        FuneralCase.company_id == current_user.company_id,
    ).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    dec = db.query(CaseDeceased).filter(CaseDeceased.case_id == case_id).first()
    if not dec:
        raise HTTPException(status_code=500, detail="Case missing deceased record")

    payload = data.dict(exclude_unset=True)
    # SSN — encrypt, never store plaintext
    if "ssn" in payload:
        ssn = payload.pop("ssn")
        if ssn:
            try:
                dec.ssn_encrypted = crypto.encrypt_ssn(ssn)
                dec.ssn_last_four = crypto.ssn_last_four(ssn)
            except crypto.EncryptionNotConfiguredError as e:
                raise HTTPException(status_code=503, detail=str(e))
        else:
            dec.ssn_encrypted = None
            dec.ssn_last_four = None

    for k, v in payload.items():
        setattr(dec, k, v)
    db.commit()
    return {"updated": True}


@router.patch("/{case_id}/service")
def update_service(
    case_id: str,
    data: UpdateServiceRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    case = db.query(FuneralCase).filter(
        FuneralCase.id == case_id,
        FuneralCase.company_id == current_user.company_id,
    ).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    svc = db.query(CaseService).filter(CaseService.case_id == case_id).first()
    if not svc:
        raise HTTPException(status_code=500, detail="Case missing service record")
    for k, v in data.dict(exclude_unset=True).items():
        setattr(svc, k, v)
    db.commit()
    return {"updated": True}


@router.get("/{case_id}/informants")
def list_informants(
    case_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = db.query(CaseInformant).filter(
        CaseInformant.case_id == case_id,
        CaseInformant.company_id == current_user.company_id,
    ).all()
    return [
        {
            "id": i.id,
            "name": i.name,
            "relationship": i.relationship,
            "phone": i.phone,
            "email": i.email,
            "address": i.address,
            "is_primary": i.is_primary,
            "is_authorizing": i.is_authorizing,
            "authorization_signed_at": i.authorization_signed_at.isoformat() if i.authorization_signed_at else None,
            "authorization_method": i.authorization_method,
        }
        for i in rows
    ]


@router.post("/{case_id}/informants")
def add_informant(
    case_id: str,
    data: AddInformantRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    case = db.query(FuneralCase).filter(
        FuneralCase.id == case_id,
        FuneralCase.company_id == current_user.company_id,
    ).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    import uuid as _u
    inf = CaseInformant(
        id=str(_u.uuid4()),
        case_id=case_id,
        company_id=current_user.company_id,
        **data.dict(),
    )
    db.add(inf)
    db.commit()
    db.refresh(inf)
    return {"id": inf.id, "name": inf.name}


@router.post("/{case_id}/informants/{informant_id}/sign")
def sign_authorization(
    case_id: str,
    informant_id: str,
    method: str = Query(..., regex="^(in_person|emailed|faxed|digital)$"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    inf = db.query(CaseInformant).filter(
        CaseInformant.id == informant_id,
        CaseInformant.case_id == case_id,
        CaseInformant.company_id == current_user.company_id,
    ).first()
    if not inf:
        raise HTTPException(status_code=404, detail="Informant not found")
    inf.authorization_signed_at = datetime.utcnow()
    inf.authorization_method = method
    db.commit()
    return {"signed": True}


# ─────────────────────────────────────────────────────────────────────────
# Notes
# ─────────────────────────────────────────────────────────────────────────

@router.get("/{case_id}/notes")
def list_notes(
    case_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    notes = (
        db.query(FuneralCaseNote)
        .filter(FuneralCaseNote.case_id == case_id, FuneralCaseNote.company_id == current_user.company_id)
        .order_by(FuneralCaseNote.created_at.desc())
        .limit(200)
        .all()
    )
    return [
        {
            "id": n.id,
            "note_type": n.note_type,
            "content": n.content,
            "author_id": n.author_id,
            "author_name": n.author_name,
            "field_key": n.field_key,
            "confidence": n.confidence,
            "created_at": n.created_at.isoformat() if n.created_at else None,
        }
        for n in notes
    ]


@router.post("/{case_id}/notes")
def add_note(
    case_id: str,
    data: AddNoteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    case = db.query(FuneralCase).filter(
        FuneralCase.id == case_id,
        FuneralCase.company_id == current_user.company_id,
    ).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    import uuid as _u
    n = FuneralCaseNote(
        id=str(_u.uuid4()),
        case_id=case_id,
        company_id=current_user.company_id,
        note_type=data.note_type,
        content=data.content,
        author_id=current_user.id,
        author_name=f"{current_user.first_name or ''} {current_user.last_name or ''}".strip() or current_user.email,
    )
    db.add(n)
    db.commit()
    return {"id": n.id}


# ─────────────────────────────────────────────────────────────────────────
# Scribe + Story Thread
# ─────────────────────────────────────────────────────────────────────────

@router.post("/{case_id}/scribe/process")
def scribe_process(
    case_id: str,
    data: ScribeProcessRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    case = db.query(FuneralCase).filter(
        FuneralCase.id == case_id,
        FuneralCase.company_id == current_user.company_id,
    ).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    try:
        return scribe_service.process_transcript(db, case_id, data.transcript, director_id=current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{case_id}/scribe/extract")
def scribe_extract(
    case_id: str,
    data: ScribeProcessRequest,   # same shape — `transcript` field carries NL text
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    case = db.query(FuneralCase).filter(
        FuneralCase.id == case_id,
        FuneralCase.company_id == current_user.company_id,
    ).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    try:
        return scribe_service.extract_from_nl(db, case_id, data.transcript, director_id=current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{case_id}/story/compile")
def compile_story(
    case_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        narrative = story_thread_service.compile_narrative(db, case_id)
        return {"narrative": narrative}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch("/{case_id}/story/approve")
def approve_all(
    case_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    case = db.query(FuneralCase).filter(
        FuneralCase.id == case_id,
        FuneralCase.company_id == current_user.company_id,
    ).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    try:
        return story_thread_service.approve_all_selections(db, case_id, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ─────────────────────────────────────────────────────────────────────────
# Briefing endpoints
# ─────────────────────────────────────────────────────────────────────────

@router.get("/-/briefing")
def briefing(
    location_id: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return {
        "active_cases": case_service.get_active_cases(
            db, current_user.company_id, location_id=location_id, limit=20
        ),
        "needs_attention": case_service.get_needs_attention(
            db, current_user.company_id, location_id=location_id
        ),
        "upcoming_services": case_service.get_upcoming_services(
            db, current_user.company_id, location_id=location_id, days_ahead=14
        ),
    }


@router.get("/-/needs-attention")
def needs_attention(
    location_id: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return case_service.get_needs_attention(db, current_user.company_id, location_id=location_id)


@router.get("/-/upcoming-services")
def upcoming_services(
    days: int = Query(14, ge=1, le=90),
    location_id: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return case_service.get_upcoming_services(
        db, current_user.company_id, location_id=location_id, days_ahead=days
    )
