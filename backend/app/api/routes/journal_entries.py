"""Journal entry API routes."""

import json
import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.journal_entry import AccountingPeriod, JournalEntry, JournalEntryLine, JournalEntryTemplate
from app.models.accounting_analysis import TenantGLMapping
from app.models.user import User

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
    total_d = sum(Decimal(str(l.debit_amount)) for l in body.lines)
    total_c = sum(Decimal(str(l.credit_amount)) for l in body.lines)

    entry = JournalEntry(
        tenant_id=current_user.company_id,
        entry_number=entry_number,
        entry_type=body.entry_type,
        entry_date=ed,
        period_month=ed.month,
        period_year=ed.year,
        description=body.description,
        reference_number=body.reference_number,
        total_debits=total_d,
        total_credits=total_c,
        reversal_scheduled=body.reversal_scheduled,
        reversal_date=date.fromisoformat(body.reversal_date) if body.reversal_date else None,
        created_by=current_user.id,
    )
    db.add(entry)
    db.flush()

    for i, line in enumerate(body.lines):
        # Denormalize GL account info
        gl = db.query(TenantGLMapping).filter(TenantGLMapping.id == line.gl_account_id).first()
        db.add(JournalEntryLine(
            tenant_id=current_user.company_id,
            journal_entry_id=entry.id,
            line_number=i + 1,
            gl_account_id=line.gl_account_id,
            gl_account_number=gl.account_number if gl else line.gl_account_number,
            gl_account_name=gl.account_name if gl else line.gl_account_name,
            description=line.description,
            debit_amount=Decimal(str(line.debit_amount)),
            credit_amount=Decimal(str(line.credit_amount)),
        ))

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

    # Check period status
    period = db.query(AccountingPeriod).filter(
        AccountingPeriod.tenant_id == current_user.company_id,
        AccountingPeriod.period_month == entry.period_month,
        AccountingPeriod.period_year == entry.period_year,
    ).first()
    if period and period.status == "closed":
        raise HTTPException(400, f"Period {entry.period_month}/{entry.period_year} is closed")

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
    today = date.today()

    reversal = JournalEntry(
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
        total_debits=original.total_credits,
        total_credits=original.total_debits,
        created_by=current_user.id,
        posted_by=current_user.id,
        posted_at=datetime.now(timezone.utc),
    )
    db.add(reversal)
    db.flush()

    orig_lines = db.query(JournalEntryLine).filter(JournalEntryLine.journal_entry_id == entry_id).all()
    for i, ol in enumerate(orig_lines):
        db.add(JournalEntryLine(
            tenant_id=current_user.company_id,
            journal_entry_id=reversal.id,
            line_number=i + 1,
            gl_account_id=ol.gl_account_id,
            gl_account_number=ol.gl_account_number,
            gl_account_name=ol.gl_account_name,
            description=ol.description,
            debit_amount=ol.credit_amount,
            credit_amount=ol.debit_amount,
        ))

    original.status = "reversed"
    db.commit()
    return {"id": reversal.id, "entry_number": rev_number, "status": "posted"}


# ── AI Parsing ──

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
        import anthropic
        client = anthropic.Anthropic()
        response = client.messages.create(
            model=JE_MODEL,
            max_tokens=500,
            system=(
                "Parse a natural language journal entry into structured debit/credit lines. "
                "Chart of accounts:\n" + accounts_text + "\n\n"
                "Rules: Assets increase with debits. Liabilities increase with credits. "
                "Revenue increases with credits. Expenses increase with debits. "
                "Every entry must balance. Return JSON only: "
                '{"description": str, "entry_date": str or null, "entry_type": str, '
                '"lines": [{"gl_account_id": str, "gl_account_number": str, "gl_account_name": str, '
                '"side": "debit"|"credit", "amount": number, "description": str or null}], '
                '"confidence": number, "clarification_needed": str or null}'
            ),
            messages=[{"role": "user", "content": body.input}],
        )
        result = json.loads(response.content[0].text)
        return result
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
