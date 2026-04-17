"""Funeral Home case service — the spine of case management.

create_case / get_staircase / advance_step / get_needs_attention.
Staircase hides irrelevant steps (veterans for non-vets, cremation for burial, etc.).
"""

import secrets
import uuid
from datetime import datetime, timezone, timedelta

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.models.funeral_case import (
    CaseAftercare,
    CaseCemetery,
    CaseCremation,
    CaseDeceased,
    CaseDisposition,
    CaseFieldConfig,
    CaseFinancials,
    CaseMerchandise,
    CasePreneed,
    CaseService,
    CaseVeteran,
    FHCaseVault,
    FuneralCase,
    FuneralCaseNote,
)


DEFAULT_STAIRCASE = [
    "arrangement_conference",
    "vital_statistics",
    "authorization",
    "service_planning",
    "obituary",
    "merchandise_vault",
    "merchandise_casket",
    "merchandise_monument",
    "merchandise_urn",
    "story",
    "cemetery",
    "cremation",
    "veterans_benefits",
    "death_certificate",
    "financials",
    "aftercare",
]

STEP_LABELS = {
    "arrangement_conference": "Arrangement Conference",
    "vital_statistics": "Vital Statistics",
    "authorization": "Authorization",
    "service_planning": "Service Planning",
    "obituary": "Obituary",
    "merchandise_vault": "Vault Selection",
    "merchandise_casket": "Casket Selection",
    "merchandise_monument": "Monument Selection",
    "merchandise_urn": "Urn Selection",
    "story": "The Story",
    "cemetery": "Cemetery",
    "cremation": "Cremation",
    "veterans_benefits": "Veterans Benefits",
    "death_certificate": "Death Certificate",
    "financials": "Financials",
    "aftercare": "Aftercare",
}


def _next_case_number(db: Session, company_id: str) -> str:
    """Generate FC-{YEAR}-{SEQUENCE} per company."""
    year = datetime.now(timezone.utc).year
    prefix = f"FC-{year}-"
    count = (
        db.query(func.count(FuneralCase.id))
        .filter(FuneralCase.company_id == company_id, FuneralCase.case_number.like(f"{prefix}%"))
        .scalar() or 0
    )
    return f"{prefix}{count + 1:04d}"


def _get_field_config(db: Session, company_id: str) -> CaseFieldConfig:
    cfg = db.query(CaseFieldConfig).filter(CaseFieldConfig.company_id == company_id).first()
    if not cfg:
        # Auto-create a default config with NY + all modules enabled
        cfg = CaseFieldConfig(
            company_id=company_id,
            default_state="NY",
            veterans_module_enabled=True,
            preneed_module_enabled=False,
            cremation_module_enabled=True,
            monument_step_enabled=True,
            casket_step_enabled=True,
        )
        db.add(cfg)
        db.commit()
        db.refresh(cfg)
    return cfg


def create_case(
    db: Session,
    company_id: str,
    director_id: str | None = None,
    location_id: str | None = None,
) -> FuneralCase:
    """Create a case with all satellite records pre-created.

    Follows the FH-1a spec: every case has its 13 domain satellites +
    a case_vault with a fresh access_token. Applies the staircase defaults
    from case_field_config.
    """
    cfg = _get_field_config(db, company_id)

    case_number = _next_case_number(db, company_id)
    case = FuneralCase(
        id=str(uuid.uuid4()),
        company_id=company_id,
        location_id=location_id,
        case_number=case_number,
        status="active",
        director_id=director_id,
        current_step="arrangement_conference",
        completed_steps=[],
        story_thread_status="building",
    )
    db.add(case)
    db.flush()

    # Create all satellite records immediately
    for Model, extra in [
        (CaseDeceased, {}),
        (CaseService, {}),
        (CaseDisposition, {}),
        (CaseCemetery, {}),
        (CaseCremation, {}),
        (CaseVeteran, {}),
        (CaseMerchandise, {}),
        (CaseFinancials, {"amount_paid": 0}),
        (CasePreneed, {}),
        (CaseAftercare, {}),
    ]:
        db.add(Model(id=str(uuid.uuid4()), case_id=case.id, company_id=company_id, **extra))

    # Vault with fresh access token
    db.add(FHCaseVault(
        id=str(uuid.uuid4()),
        case_id=case.id,
        company_id=company_id,
        access_token=secrets.token_urlsafe(32),
        is_active=True,
    ))

    # Record case-opened note
    db.add(FuneralCaseNote(
        id=str(uuid.uuid4()),
        case_id=case.id,
        company_id=company_id,
        note_type="system",
        content=f"Case {case_number} opened",
        author_id=director_id,
    ))

    db.commit()
    db.refresh(case)
    return case


def _step_is_hidden(step_key: str, case_id: str, db: Session) -> bool:
    """Return True if this step should be hidden for this case."""
    # merchandise_urn, cremation: only if disposition is cremation
    # cemetery: only if burial or entombment
    # veterans_benefits: only if veteran
    if step_key in ("merchandise_urn", "cremation"):
        disp = db.query(CaseDisposition).filter(CaseDisposition.case_id == case_id).first()
        return not disp or (disp.disposition_type or "").lower() != "cremation"
    if step_key == "cemetery":
        disp = db.query(CaseDisposition).filter(CaseDisposition.case_id == case_id).first()
        if not disp:
            return False  # default to visible until disposition set
        return (disp.disposition_type or "").lower() not in ("", "burial", "entombment")
    if step_key == "veterans_benefits":
        vet = db.query(CaseVeteran).filter(CaseVeteran.case_id == case_id).first()
        return not vet or not vet.ever_in_armed_forces
    return False


def get_staircase(db: Session, case_id: str) -> list[dict]:
    """Return the ordered staircase for a case, with hidden steps filtered out.

    Each entry: key, name, status (completed|current|pending), is_current,
    domain_table (loose mapping), completion_percentage (heuristic).
    """
    case = db.query(FuneralCase).filter(FuneralCase.id == case_id).first()
    if not case:
        raise ValueError("Case not found")

    cfg = _get_field_config(db, case.company_id)
    config_order = cfg.staircase_config or {}
    raw_steps = config_order.get("steps", DEFAULT_STAIRCASE) if isinstance(config_order, dict) else DEFAULT_STAIRCASE

    completed = set(case.completed_steps or [])
    current_step = case.current_step

    # Module toggles from config
    skip_keys = set()
    if not cfg.veterans_module_enabled:
        skip_keys.add("veterans_benefits")
    if not cfg.cremation_module_enabled:
        skip_keys |= {"cremation", "merchandise_urn"}
    if not cfg.monument_step_enabled:
        skip_keys.add("merchandise_monument")
    if not cfg.casket_step_enabled:
        skip_keys.add("merchandise_casket")

    out = []
    for key in raw_steps:
        if key in skip_keys:
            continue
        if _step_is_hidden(key, case_id, db):
            continue
        if key in completed:
            status = "completed"
        elif key == current_step:
            status = "current"
        else:
            status = "pending"
        out.append({
            "key": key,
            "name": STEP_LABELS.get(key, key.replace("_", " ").title()),
            "status": status,
            "is_current": key == current_step,
        })
    return out


def advance_step(db: Session, case_id: str, step_key: str) -> FuneralCase:
    """Mark the given step complete and move current_step to the next visible step."""
    case = db.query(FuneralCase).filter(FuneralCase.id == case_id).first()
    if not case:
        raise ValueError("Case not found")

    staircase = get_staircase(db, case_id)
    keys_in_order = [s["key"] for s in staircase]

    completed = list(case.completed_steps or [])
    if step_key not in completed:
        completed.append(step_key)
    case.completed_steps = completed

    # Find next step
    try:
        idx = keys_in_order.index(step_key)
        if idx + 1 < len(keys_in_order):
            case.current_step = keys_in_order[idx + 1]
        else:
            case.current_step = "aftercare"
            case.status = "completed"
            case.completed_at = datetime.now(timezone.utc)
    except ValueError:
        pass

    # System note
    db.add(FuneralCaseNote(
        id=str(uuid.uuid4()),
        case_id=case_id,
        company_id=case.company_id,
        note_type="system",
        content=f"Step completed: {STEP_LABELS.get(step_key, step_key)}",
    ))

    db.commit()
    db.refresh(case)
    return case


def get_needs_attention(
    db: Session,
    company_id: str,
    director_id: str | None = None,
    location_id: str | None = None,
) -> list[dict]:
    """Return cases needing attention: unsigned auth, unfiled DC, stuck > 7 days."""
    q = db.query(FuneralCase).filter(
        FuneralCase.company_id == company_id,
        FuneralCase.status == "active",
    )
    if director_id:
        q = q.filter(FuneralCase.director_id == director_id)
    if location_id:
        q = q.filter(FuneralCase.location_id == location_id)

    cases = q.all()
    out = []
    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)

    for case in cases:
        reasons = []

        # Unsigned authorization — at least one authorizing informant with no signature
        from app.models.funeral_case import CaseInformant
        auth_needed = (
            db.query(CaseInformant)
            .filter(
                CaseInformant.case_id == case.id,
                CaseInformant.is_authorizing == True,  # noqa: E712
                CaseInformant.authorization_signed_at.is_(None),
            )
            .count()
        )
        if auth_needed > 0:
            reasons.append("Authorization unsigned")

        # Death certificate not filed
        disp = db.query(CaseDisposition).filter(CaseDisposition.case_id == case.id).first()
        if disp and disp.death_certificate_status in ("not_filed", None):
            reasons.append("Death certificate not filed")

        # Stuck on same step > 7 days
        if case.opened_at and case.opened_at < seven_days_ago and not case.completed_steps:
            reasons.append(f"No progress since opened")

        if reasons:
            # Get deceased name for display
            dec = db.query(CaseDeceased).filter(CaseDeceased.case_id == case.id).first()
            name_parts = [p for p in [dec.first_name, dec.last_name] if p] if dec else []
            name = " ".join(name_parts) or case.case_number
            days_open = (datetime.now(timezone.utc) - case.opened_at).days if case.opened_at else 0
            out.append({
                "case_id": case.id,
                "case_number": case.case_number,
                "deceased_name": name,
                "reasons": reasons,
                "days_open": days_open,
                "current_step": case.current_step,
            })

    # Most urgent first: multiple reasons > 1 reason
    out.sort(key=lambda r: (-len(r["reasons"]), -r["days_open"]))
    return out


def get_active_cases(
    db: Session,
    company_id: str,
    director_id: str | None = None,
    location_id: str | None = None,
    limit: int = 50,
) -> list[dict]:
    q = db.query(FuneralCase).filter(
        FuneralCase.company_id == company_id,
        FuneralCase.status == "active",
    )
    if director_id:
        q = q.filter(FuneralCase.director_id == director_id)
    if location_id:
        q = q.filter(FuneralCase.location_id == location_id)
    cases = q.order_by(FuneralCase.opened_at.desc()).limit(limit).all()

    out = []
    for case in cases:
        dec = db.query(CaseDeceased).filter(CaseDeceased.case_id == case.id).first()
        name = " ".join([p for p in [dec.first_name, dec.last_name] if p]) if dec else case.case_number
        days_open = (datetime.now(timezone.utc) - case.opened_at).days if case.opened_at else 0
        out.append({
            "case_id": case.id,
            "case_number": case.case_number,
            "deceased_name": name or case.case_number,
            "current_step": case.current_step,
            "current_step_label": STEP_LABELS.get(case.current_step, case.current_step),
            "days_open": days_open,
            "director_id": case.director_id,
            "location_id": case.location_id,
        })
    return out


def get_upcoming_services(
    db: Session,
    company_id: str,
    location_id: str | None = None,
    days_ahead: int = 14,
) -> list[dict]:
    """Upcoming services in the next N days, oldest-first."""
    from datetime import date
    today = date.today()
    window_end = today + timedelta(days=days_ahead)

    q = (
        db.query(FuneralCase, CaseService, CaseDeceased)
        .join(CaseService, CaseService.case_id == FuneralCase.id)
        .join(CaseDeceased, CaseDeceased.case_id == FuneralCase.id)
        .filter(FuneralCase.company_id == company_id)
        .filter(CaseService.service_date >= today)
        .filter(CaseService.service_date <= window_end)
        .order_by(CaseService.service_date, CaseService.service_time)
    )
    if location_id:
        q = q.filter(FuneralCase.location_id == location_id)

    out = []
    for case, service, dec in q.all():
        name = " ".join([p for p in [dec.first_name, dec.last_name] if p]) or case.case_number
        out.append({
            "case_id": case.id,
            "case_number": case.case_number,
            "deceased_name": name,
            "service_date": service.service_date.isoformat() if service.service_date else None,
            "service_time": service.service_time.isoformat() if service.service_time else None,
            "service_location_name": service.service_location_name,
            "service_type": service.service_type,
        })
    return out


def get_case_detail(db: Session, case_id: str, include_ssn: bool = False) -> dict:
    """Fetch full case detail for the dashboard. SSN masked by default."""
    from app.services.fh.crypto import decrypt_ssn, mask_ssn_display

    case = db.query(FuneralCase).filter(FuneralCase.id == case_id).first()
    if not case:
        raise ValueError("Case not found")

    dec = db.query(CaseDeceased).filter(CaseDeceased.case_id == case_id).first()
    service = db.query(CaseService).filter(CaseService.case_id == case_id).first()
    disp = db.query(CaseDisposition).filter(CaseDisposition.case_id == case_id).first()
    cem = db.query(CaseCemetery).filter(CaseCemetery.case_id == case_id).first()
    vet = db.query(CaseVeteran).filter(CaseVeteran.case_id == case_id).first()
    merch = db.query(CaseMerchandise).filter(CaseMerchandise.case_id == case_id).first()
    fin = db.query(CaseFinancials).filter(CaseFinancials.case_id == case_id).first()

    from app.models.funeral_case import CaseInformant
    informants = db.query(CaseInformant).filter(CaseInformant.case_id == case_id).all()

    ssn_display = "•••-••-••••"
    ssn_plain = None
    if dec and dec.ssn_last_four:
        ssn_display = mask_ssn_display(dec.ssn_last_four)
        if include_ssn and dec.ssn_encrypted:
            try:
                ssn_plain = decrypt_ssn(dec.ssn_encrypted)
            except Exception:
                ssn_plain = None

    return {
        "case": {
            "id": case.id,
            "case_number": case.case_number,
            "status": case.status,
            "current_step": case.current_step,
            "completed_steps": case.completed_steps or [],
            "director_id": case.director_id,
            "location_id": case.location_id,
            "opened_at": case.opened_at.isoformat() if case.opened_at else None,
            "days_open": (datetime.now(timezone.utc) - case.opened_at).days if case.opened_at else 0,
            "story_thread_status": case.story_thread_status,
            "vault_manufacturer_company_id": case.vault_manufacturer_company_id,
            "cemetery_company_id": case.cemetery_company_id,
        },
        "deceased": {
            "id": dec.id if dec else None,
            "first_name": dec.first_name if dec else None,
            "middle_name": dec.middle_name if dec else None,
            "last_name": dec.last_name if dec else None,
            "suffix": dec.suffix if dec else None,
            "date_of_birth": dec.date_of_birth.isoformat() if dec and dec.date_of_birth else None,
            "date_of_death": dec.date_of_death.isoformat() if dec and dec.date_of_death else None,
            "sex": dec.sex if dec else None,
            "religion": dec.religion if dec else None,
            "occupation": dec.occupation if dec else None,
            "ssn_display": ssn_display,
            "ssn_plaintext": ssn_plain,   # only non-null if include_ssn=True was requested
        } if dec else None,
        "service": {
            "service_type": service.service_type if service else None,
            "service_date": service.service_date.isoformat() if service and service.service_date else None,
            "service_time": service.service_time.isoformat() if service and service.service_time else None,
            "service_location_name": service.service_location_name if service else None,
            "officiant_name": service.officiant_name if service else None,
        } if service else None,
        "disposition": {
            "disposition_type": disp.disposition_type if disp else None,
            "death_certificate_status": disp.death_certificate_status if disp else "not_filed",
        } if disp else None,
        "cemetery": {
            "cemetery_name": cem.cemetery_name if cem else None,
            "section": cem.section if cem else None,
            "row": cem.row if cem else None,
            "plot_number": cem.plot_number if cem else None,
        } if cem else None,
        "veteran": {
            "ever_in_armed_forces": vet.ever_in_armed_forces if vet else False,
            "branch": vet.branch if vet else None,
            "dd214_on_file": vet.dd214_on_file if vet else False,
            "va_flag_requested": vet.va_flag_requested if vet else False,
        } if vet else None,
        "informants": [
            {
                "id": i.id,
                "name": i.name,
                "relationship": i.relationship,
                "phone": i.phone,
                "email": i.email,
                "is_primary": i.is_primary,
                "is_authorizing": i.is_authorizing,
                "authorization_signed_at": i.authorization_signed_at.isoformat() if i.authorization_signed_at else None,
            }
            for i in informants
        ],
        "merchandise": {
            "vault_product_name": merch.vault_product_name if merch else None,
            "vault_approved_at": merch.vault_approved_at.isoformat() if merch and merch.vault_approved_at else None,
            "casket_product_name": merch.casket_product_name if merch else None,
            "casket_approved_at": merch.casket_approved_at.isoformat() if merch and merch.casket_approved_at else None,
            "monument_shape": merch.monument_shape if merch else None,
            "monument_approved_at": merch.monument_approved_at.isoformat() if merch and merch.monument_approved_at else None,
        } if merch else None,
        "financials": {
            "total": float(fin.total) if fin and fin.total else 0,
            "amount_paid": float(fin.amount_paid) if fin and fin.amount_paid else 0,
            "balance_due": float(fin.balance_due) if fin and fin.balance_due else 0,
        } if fin else None,
    }
