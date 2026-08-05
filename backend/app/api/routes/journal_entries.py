"""Journal entry API routes."""

import json
import logging
import uuid
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.journal_entry import AccountingPeriod, JournalEntry, JournalEntryLine, JournalEntryTemplate
from app.models.accounting_analysis import TenantGLMapping
from app.models.user import User
from app.services import journal_entry_service, reconciliation_gl
from app.services.journal_entry_service import JournalLineSpec
from app.services.agents.period_lock import PeriodLockService, PeriodLockedError

logger = logging.getLogger(__name__)
router = APIRouter()

JE_MODEL = "claude-haiku-4-5-20250514"


# ── Schemas ──

class JELineCreate(BaseModel):
    gl_account_id: str
    gl_account_number: str | None = None
    gl_account_name: str | None = None
    description: str | None = None
    debit_amount: float = 0
    credit_amount: float = 0


class JECreate(BaseModel):
    entry_type: str = "manual"
    entry_date: str
    description: str
    reference_number: str | None = None
    reversal_scheduled: bool = False
    reversal_date: str | None = None
    lines: list[JELineCreate]


class ParseRequest(BaseModel):
    input: str


class TemplateCreate(BaseModel):
    template_name: str
    description: str | None = None
    entry_type: str = "recurring"
    frequency: str = "monthly"
    day_of_month: int | None = None
    months_of_year: list[int] | None = None
    auto_post: bool = False
    auto_reverse: bool = False
    reverse_days_after: int = 1
    template_lines: list[dict]


class PeriodAction(BaseModel):
    period_month: int
    period_year: int
    reason: str | None = None


# ── Entry CRUD ──

@router.get("/entries")
def list_entries(
    period_month: int | None = Query(None),
    period_year: int | None = Query(None),
    status: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(JournalEntry).filter(JournalEntry.tenant_id == current_user.company_id)
    if period_month and period_year:
        query = query.filter(JournalEntry.period_month == period_month, JournalEntry.period_year == period_year)
    if status:
        query = query.filter(JournalEntry.status == status)
    entries = query.order_by(JournalEntry.entry_date.desc()).limit(100).all()
    return [_serialize_entry(e) for e in entries]


@router.post("/entries")
def create_entry(
    body: JECreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Generate entry number
    count = db.query(func.count(JournalEntry.id)).filter(JournalEntry.tenant_id == current_user.company_id).scalar() or 0
    entry_number = f"JE-{count + 1001}"

    ed = date.fromisoformat(body.entry_date)

    # Resolve + validate each line's GL BEFORE constructing anything.
    # SCOPE the lookup by tenant_id (a GL id is only meaningful within the
    # caller's own tenant) AND require a match — an unresolved
    # gl_account_id is a 400, never a silent fallback. Pre-fix this
    # filtered on id alone, so a foreign tenant's account_number/name could
    # be denormalized onto the line (a cross-tenant read), and an unknown
    # id left silent nulls; both are now rejected. Security-adjacent — see
    # the JE characterization test.
    line_specs: list[JournalLineSpec] = []
    for line in body.lines:
        # L-2.2 X-1: was a local `tenant_id`-only filter, which accepted a
        # soft-deleted mapping that `validate_gl_account` — the single
        # definition of a usable GL account everywhere else — refuses. Two
        # definitions differing by one predicate is the drift L-2.1b closed on
        # the reconciliation routes; this closes it here.
        gl = reconciliation_gl.require_gl_account(
            db, current_user.company_id, line.gl_account_id
        )
        line_specs.append(JournalLineSpec(
            gl_account_id=line.gl_account_id,
            gl_account_number=gl.account_number,
            gl_account_name=gl.account_name,
            description=line.description,
            debit_amount=line.debit_amount,
            credit_amount=line.credit_amount,
        ))

    entry = journal_entry_service.create_journal_entry(
        db,
        tenant_id=current_user.company_id,
        entry_number=entry_number,
        entry_type=body.entry_type,
        entry_date=ed,
        period_month=ed.month,
        period_year=ed.year,
        description=body.description,
        reference_number=body.reference_number,
        reversal_scheduled=body.reversal_scheduled,
        reversal_date=date.fromisoformat(body.reversal_date) if body.reversal_date else None,
        created_by=current_user.id,
        lines=line_specs,
    )

    db.commit()
    db.refresh(entry)
    return {"id": entry.id, "entry_number": entry_number, "status": entry.status}


@router.get("/entries/{entry_id}")
def get_entry(
    entry_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    entry = db.query(JournalEntry).filter(
        JournalEntry.id == entry_id, JournalEntry.tenant_id == current_user.company_id,
    ).first()
    if not entry:
        raise HTTPException(404, "Entry not found")
    lines = db.query(JournalEntryLine).filter(JournalEntryLine.journal_entry_id == entry_id).order_by(JournalEntryLine.line_number).all()
    return {
        **_serialize_entry(entry),
        "lines": [
            {
                "id": l.id, "line_number": l.line_number,
                "gl_account_id": l.gl_account_id,
                "gl_account_number": l.gl_account_number,
                "gl_account_name": l.gl_account_name,
                "description": l.description,
                "debit_amount": float(l.debit_amount),
                "credit_amount": float(l.credit_amount),
            }
            for l in lines
        ],
    }


@router.post("/entries/{entry_id}/post")
def post_entry(
    entry_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    entry = db.query(JournalEntry).filter(
        JournalEntry.id == entry_id, JournalEntry.tenant_id == current_user.company_id,
    ).first()
    if not entry:
        raise HTTPException(404, "Entry not found")
    if entry.status not in ("draft", "pending_review"):
        raise HTTPException(400, f"Cannot post entry with status '{entry.status}'")

    # Validate balance
    if entry.total_debits != entry.total_credits:
        raise HTTPException(400, f"Entry is not balanced. Debits: ${entry.total_debits}, Credits: ${entry.total_credits}")

    lines = db.query(JournalEntryLine).filter(JournalEntryLine.journal_entry_id == entry_id).all()
    if len(lines) < 2:
        raise HTTPException(400, "At least 2 lines required")

    # Check period status — BOTH closed-period sources, closed-if-either
    # (fail-closed while the two tables coexist). AccountingPeriod is the
    # JE module's manual month/year close; PeriodLock is the authoritative
    # platform lock that month-end close writes and every AR write honors.
    # S-3 ADDED the PeriodLock check ALONGSIDE (not in place of) the
    # AccountingPeriod one — dropping AccountingPeriod would silently
    # re-permit posting into a manually-closed period. Reconciling the two
    # tables (are there closed AccountingPeriods with no PeriodLock?) is an
    # S-6 item with a data question that must be answered before either is
    # retired.
    period = db.query(AccountingPeriod).filter(
        AccountingPeriod.tenant_id == current_user.company_id,
        AccountingPeriod.period_month == entry.period_month,
        AccountingPeriod.period_year == entry.period_year,
    ).first()
    if period and period.status == "closed":
        raise HTTPException(400, f"Period {entry.period_month}/{entry.period_year} is closed")
    lock = PeriodLockService.check_date_in_locked_period(
        db, current_user.company_id, entry.entry_date
    )
    if lock:
        raise PeriodLockedError(lock)

    entry.status = "posted"
    entry.posted_by = current_user.id
    entry.posted_at = datetime.now(timezone.utc)
    db.commit()
    return {"status": "posted"}


@router.post("/entries/{entry_id}/reverse")
def reverse_entry(
    entry_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    original = db.query(JournalEntry).filter(
        JournalEntry.id == entry_id, JournalEntry.tenant_id == current_user.company_id,
    ).first()
    if not original or original.status != "posted":
        raise HTTPException(400, "Can only reverse posted entries")

    # Generate reversal
    count = db.query(func.count(JournalEntry.id)).filter(JournalEntry.tenant_id == current_user.company_id).scalar() or 0
    rev_number = f"JE-{count + 1001}"
    # A reversal posts in the CURRENT period (today), not the original's
    # period — standard practice: you reverse a closed-period entry INTO the
    # open current period, you do not reach back. This `today` is CORRECT,
    # NOT the entry_date/period-derivation inconsistency to "unify" away. A
    # later cleanup that copies the original's entry_date here would turn
    # correct behavior into a bug AND would trip the S-3 period-lock guard on
    # every reversal of a locked-period entry (making a legitimate operation
    # impossible). Leave it as today.
    today = date.today()

    # Mirror the original's lines (debit <-> credit). The service computes
    # the reversal totals from these mirrored specs, which equals the
    # original's swapped totals exactly.
    orig_lines = db.query(JournalEntryLine).filter(JournalEntryLine.journal_entry_id == entry_id).all()
    rev_specs = [
        JournalLineSpec(
            gl_account_id=ol.gl_account_id,
            gl_account_number=ol.gl_account_number,
            gl_account_name=ol.gl_account_name,
            description=ol.description,
            debit_amount=ol.credit_amount,
            credit_amount=ol.debit_amount,
        )
        for ol in orig_lines
    ]

    reversal = journal_entry_service.create_journal_entry(
        db,
        tenant_id=current_user.company_id,
        entry_number=rev_number,
        entry_type="reversal",
        status="posted",
        entry_date=today,
        period_month=today.month,
        period_year=today.year,
        description=f"Reversal of {original.entry_number}: {original.description}",
        is_reversal=True,
        reversal_of_entry_id=original.id,
        created_by=current_user.id,
        posted_by=current_user.id,
        posted_at=datetime.now(timezone.utc),
        lines=rev_specs,
    )

    original.status = "reversed"
    db.commit()
    return {"id": reversal.id, "entry_number": rev_number, "status": "posted"}


# ── AI Parsing ──

def _resolve_parsed_lines(db: Session, tenant_id: str, parsed: dict) -> dict:
    """Resolve every GL account the model proposed against THIS tenant's chart.

    L-2.2 X-2. `parse_entry` used to return the model's output verbatim, so a
    `gl_account_id` it invented reached the form, sat in state invisibly, and
    surfaced as a 400 from `create_entry` at save.

    THE ID WAS ALWAYS INVENTED. The prompt renders the chart as
    ``- {account_number}: {account_name} ({category})`` and then asks for
    `gl_account_id` — the model is never shown an id, so it cannot return one.
    The ACCOUNT NUMBER is the identifier it actually has, which is why that is
    what resolution keys on. Validating the id alone would have been correct and
    useless: every line would fail.

    Order: a genuinely valid id wins (cheap, and future-proof if the prompt ever
    gains ids), then the account number, then the line is marked unresolved.

    UNRESOLVED IS FLAGGED, NOT DROPPED. `gl_account_id` goes to null so nothing
    downstream can act on a bad value, and `gl_account_unresolved` carries what
    the model proposed so the UI can say a suggestion was made and rejected.
    Dropping it silently would discard information the model produced and leave
    the operator with an empty picker and no reason for it.

    Number lookup is TENANT-SCOPED and active-only — account numbers are not
    globally unique, so an unscoped match would be a cross-tenant read.
    """
    lines = parsed.get("lines")
    if not isinstance(lines, list):
        return parsed

    out_lines = []
    for line in lines:
        if not isinstance(line, dict):
            out_lines.append(line)
            continue
        line = dict(line)
        proposed_number = line.get("gl_account_number")
        proposed_name = line.get("gl_account_name")

        gl = reconciliation_gl.validate_gl_account(
            db, tenant_id, line.get("gl_account_id")
        )
        if gl is None and proposed_number:
            gl = (
                db.query(TenantGLMapping)
                .filter(
                    TenantGLMapping.tenant_id == tenant_id,
                    TenantGLMapping.account_number == str(proposed_number),
                    TenantGLMapping.is_active.is_(True),
                )
                .first()
            )

        if gl is None:
            line["gl_account_id"] = None
            line["gl_account_number"] = None
            line["gl_account_name"] = None
            line["gl_account_unresolved"] = {
                "proposed_number": proposed_number,
                "proposed_name": proposed_name,
            }
        else:
            # Denormalize from the MAPPING, never from what the model asserted
            # about it — the same rule create_entry follows.
            line["gl_account_id"] = gl.id
            line["gl_account_number"] = gl.account_number
            line["gl_account_name"] = gl.account_name
            line["gl_account_unresolved"] = None
        out_lines.append(line)

    parsed = dict(parsed)
    parsed["lines"] = out_lines
    parsed["unresolved_line_count"] = sum(
        1 for l in out_lines
        if isinstance(l, dict) and l.get("gl_account_unresolved")
    )
    return parsed


@router.post("/entries/parse")
def parse_entry(
    body: ParseRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    gl_accounts = db.query(TenantGLMapping).filter(
        TenantGLMapping.tenant_id == current_user.company_id, TenantGLMapping.is_active == True,
    ).all()
    accounts_text = "\n".join(f"- {a.account_number}: {a.account_name} ({a.platform_category})" for a in gl_accounts)

    try:
        # Phase 2c-2 migration — accounting.parse_journal_entry
        from app.services.intelligence import intelligence_service

        result = intelligence_service.execute(
            db,
            prompt_key="accounting.parse_journal_entry",
            variables={"accounts_text": accounts_text, "input": body.input},
            company_id=current_user.company_id,
            caller_module="journal_entries.parse_entry",
            caller_entity_type="journal_entry",
            caller_entity_id=None,  # draft not yet persisted
        )
        if result.status == "success" and isinstance(result.response_parsed, dict):
            return _resolve_parsed_lines(
                db, current_user.company_id, result.response_parsed
            )
        return {
            "error": result.error_message or f"status={result.status}",
            "confidence": 0,
            "lines": [],
        }
    except Exception as e:
        logger.error(f"JE parse failed: {e}")
        return {"error": str(e), "confidence": 0, "lines": []}


# ── Templates ──

@router.get("/templates")
def list_templates(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    templates = db.query(JournalEntryTemplate).filter(
        JournalEntryTemplate.tenant_id == current_user.company_id,
    ).order_by(JournalEntryTemplate.template_name).all()
    return [
        {
            "id": t.id, "template_name": t.template_name, "entry_type": t.entry_type,
            "frequency": t.frequency, "is_active": t.is_active, "auto_post": t.auto_post,
            "next_run_date": str(t.next_run_date) if t.next_run_date else None,
            "last_run_date": str(t.last_run_date) if t.last_run_date else None,
        }
        for t in templates
    ]


@router.post("/templates")
def create_template(
    body: TemplateCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    template = JournalEntryTemplate(
        tenant_id=current_user.company_id,
        template_name=body.template_name,
        description=body.description,
        entry_type=body.entry_type,
        frequency=body.frequency,
        day_of_month=body.day_of_month,
        months_of_year=body.months_of_year,
        auto_post=body.auto_post,
        auto_reverse=body.auto_reverse,
        reverse_days_after=body.reverse_days_after,
        template_lines=body.template_lines,
        created_by=current_user.id,
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return {"id": template.id}


# ── Periods ──

@router.get("/periods")
def list_periods(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    periods = db.query(AccountingPeriod).filter(
        AccountingPeriod.tenant_id == current_user.company_id,
    ).order_by(AccountingPeriod.period_year.desc(), AccountingPeriod.period_month.desc()).limit(24).all()

    # If no periods exist, create current and last 2 months
    if not periods:
        today = date.today()
        for i in range(3):
            m = today.month - i
            y = today.year
            if m <= 0:
                m += 12
                y -= 1
            db.add(AccountingPeriod(tenant_id=current_user.company_id, period_month=m, period_year=y))
        db.commit()
        periods = db.query(AccountingPeriod).filter(
            AccountingPeriod.tenant_id == current_user.company_id,
        ).order_by(AccountingPeriod.period_year.desc(), AccountingPeriod.period_month.desc()).all()

    return [
        {
            "id": p.id, "period_month": p.period_month, "period_year": p.period_year,
            "status": p.status,
            "closed_at": p.closed_at.isoformat() if p.closed_at else None,
        }
        for p in periods
    ]


@router.post("/periods/close")
def close_period(
    body: PeriodAction,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    period = db.query(AccountingPeriod).filter(
        AccountingPeriod.tenant_id == current_user.company_id,
        AccountingPeriod.period_month == body.period_month,
        AccountingPeriod.period_year == body.period_year,
    ).first()
    if not period:
        period = AccountingPeriod(
            tenant_id=current_user.company_id,
            period_month=body.period_month,
            period_year=body.period_year,
        )
        db.add(period)
        db.flush()
    period.status = "closed"
    period.closed_by = current_user.id
    period.closed_at = datetime.now(timezone.utc)
    db.commit()
    return {"status": "closed"}


@router.post("/periods/open")
def open_period(
    body: PeriodAction,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    period = db.query(AccountingPeriod).filter(
        AccountingPeriod.tenant_id == current_user.company_id,
        AccountingPeriod.period_month == body.period_month,
        AccountingPeriod.period_year == body.period_year,
    ).first()
    if period:
        period.status = "open"
        period.closed_by = None
        period.closed_at = None
        db.commit()
    return {"status": "open"}


# ── GL Accounts (for form dropdowns) ──

@router.get("/gl-accounts")
def list_gl_accounts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    accounts = db.query(TenantGLMapping).filter(
        TenantGLMapping.tenant_id == current_user.company_id,
        TenantGLMapping.is_active == True,
    ).order_by(TenantGLMapping.account_number).all()
    return [
        {"id": a.id, "account_number": a.account_number, "account_name": a.account_name, "category": a.platform_category}
        for a in accounts
    ]


# ── Helpers ──

def _serialize_entry(e: JournalEntry) -> dict:
    return {
        "id": e.id, "entry_number": e.entry_number, "entry_type": e.entry_type,
        "status": e.status, "entry_date": str(e.entry_date),
        "period_month": e.period_month, "period_year": e.period_year,
        "description": e.description, "reference_number": e.reference_number,
        "total_debits": float(e.total_debits), "total_credits": float(e.total_credits),
        "is_reversal": e.is_reversal, "reversal_of_entry_id": e.reversal_of_entry_id,
        "reversal_scheduled": e.reversal_scheduled,
        "reversal_date": str(e.reversal_date) if e.reversal_date else None,
        "posted_at": e.posted_at.isoformat() if e.posted_at else None,
    }
