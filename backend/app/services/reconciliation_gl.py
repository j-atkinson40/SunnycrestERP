"""GL-account resolution for reconciliation postings (Ledger Posting arc L-1).

Two resolvers + one shared validator. Every one resolves-at-use and fails by
returning ``None`` — never a guess, never a partial post:

  * ``resolve_keyword_gl_account`` — the per-tenant keyword→GL map for the
    ladder's classifications (``bank_fee`` / ``payroll`` / ``nsf``). Stored as a
    settings key on ``Company.settings`` (Option A, ratified 2026-08-04), the
    EPD precedent: a tenant's GL choice for a purpose lives in settings as a
    ``TenantGLMapping.id``, resolved + validated at use.
  * ``resolve_contra_gl_account`` — a bank account's own GL (cash) account
    (``FinancialAccount.gl_account_id``, FK'd to ``tenant_gl_mappings`` in r153).
    This is the offsetting leg of every reconciliation JE.
  * ``validate_gl_account`` — the shared gate: an id resolves ONLY to an ACTIVE
    ``TenantGLMapping`` owned by THIS tenant, else ``None``.

DISCIPLINE (the whole point of the Ledger Posting arc): a ``None`` from any
resolver means the caller MUST NOT book silently. The row is raised to an
exception (L-2 keyword auto-clear) or the accept is refused (L-3 coding) —
nothing clears unbooked. The three failure modes — unmapped (no settings entry),
dangling (id points at a deleted/inactive mapping), and foreign (id belongs to
another tenant) — all fail closed; they are logged distinctly because they call
for different operator actions (configure vs. re-map vs. investigate), but none
is ever a silent clear.

Settings shape::

    company.settings["reconciliation_keyword_gl"] = {
        "bank_fee": "<TenantGLMapping.id>",
        "payroll":  "<TenantGLMapping.id>",
        "nsf":      "<TenantGLMapping.id>",
    }

An absent map, an absent key, ``None``, or an id that fails validation each
resolve to ``None``.
"""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.models.accounting_analysis import TenantGLMapping
from app.models.company import Company
from app.models.financial_account import FinancialAccount

logger = logging.getLogger(__name__)

# The settings key holding the keyword→GL map.
KEYWORD_GL_SETTINGS_KEY = "reconciliation_keyword_gl"

# The keyword ladder's classifications (reconciliation_service.py). Fixed in
# code — the settings map keys off these exact strings. The keyword vocabulary
# lives here, not in a table, precisely because it is code-fixed (that is why
# Option A over a table for three rows).
KEYWORD_CLASSIFICATIONS: tuple[str, ...] = ("bank_fee", "payroll", "nsf")


def validate_gl_account(
    db: Session, tenant_id: str, gl_account_id: str | None
) -> TenantGLMapping | None:
    """Return the ACTIVE ``TenantGLMapping`` for ``gl_account_id`` owned by
    ``tenant_id``, or ``None``. This is the single gate all resolution passes
    through — deleted, inactive, foreign-tenant, or empty all yield ``None``."""
    if not gl_account_id:
        return None
    return (
        db.query(TenantGLMapping)
        .filter(
            TenantGLMapping.id == gl_account_id,
            TenantGLMapping.tenant_id == tenant_id,
            TenantGLMapping.is_active.is_(True),
        )
        .first()
    )


def resolve_keyword_gl_account(
    db: Session, company: Company, classification: str
) -> str | None:
    """The validated GL account id for a keyword ``classification``, or ``None``.

    ``None`` ⇒ the caller raises the row to an exception (never a silent clear).
    Distinguishes unmapped (no settings entry) from dangling (mapped but the id
    no longer resolves) in the log, because they need different operator action;
    both fail closed.
    """
    if classification not in KEYWORD_CLASSIFICATIONS:
        # A classification the map has no business answering for — treat as
        # unmapped rather than trusting an arbitrary settings key.
        return None
    mapping = (company.settings or {}).get(KEYWORD_GL_SETTINGS_KEY) or {}
    gl_id = mapping.get(classification)
    if not gl_id:
        logger.info(
            "recon keyword GL unmapped: tenant=%s classification=%s",
            company.id, classification,
        )
        return None
    validated = validate_gl_account(db, company.id, gl_id)
    if validated is None:
        logger.warning(
            "recon keyword GL DANGLING: tenant=%s classification=%s gl_id=%s "
            "(deleted/inactive/foreign mapping) — will exception, not clear",
            company.id, classification, gl_id,
        )
        return None
    return validated.id


def resolve_contra_gl_account(
    db: Session, financial_account: FinancialAccount
) -> str | None:
    """The validated GL (cash) account id for a bank account, or ``None``.

    ``None`` ⇒ the JE has no offsetting leg and MUST NOT be built — the caller
    refuses the booking (row → exception, or accept rejected), never a one-legged
    or silent post.
    """
    gl_id = financial_account.gl_account_id
    if not gl_id:
        logger.info(
            "recon contra GL unset: financial_account=%s tenant=%s",
            financial_account.id, financial_account.tenant_id,
        )
        return None
    validated = validate_gl_account(db, financial_account.tenant_id, gl_id)
    if validated is None:
        logger.warning(
            "recon contra GL DANGLING: financial_account=%s gl_id=%s "
            "(deleted/inactive/foreign mapping) — refusing booking",
            financial_account.id, gl_id,
        )
        return None
    return validated.id
