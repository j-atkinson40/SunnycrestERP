"""INV-1 A-1 — which accounts an invoice would post to.

    Dr <the tenant's AR control account>    Cr <the tenant's revenue account>

A-1 RESOLVES THE LEGS AND POSTS NOTHING. `post_invoice` is A-2. This module
exists on its own so the account question can be settled, tested and reviewed
before anything writes to the ledger — the resolution is where the fail-closed
ruling lives, and the posting is mechanical once it holds.

⚠️ WHY THIS IS THE MIRROR OF `ar_payment_posting` AND NOT AN ADDITION TO IT.
The two are opposite faces of the same account: a payment books
`Dr bank / Cr AR`, an invoice books `Dr AR / Cr revenue`. Same shape, same
BLOCK_* vocabulary, same `(leg, leg, reason)` return — so a reader who has seen
one can read the other. What they must NOT share is a single function branching
on which event it is, which is the "two functions wearing one name" the
`/keyword-gl` vs `/accounting-gl` split already refused.

⚠️ FAIL-CLOSED ON THE LEDGER, FAIL-OPEN ON THE RECORD — AR-2's ruling, and the
invoice sits on the same side of it as the payment. An invoice is a document the
tenant has issued; refusing to record it does not un-issue it, and a customer
who has been billed still owes. So the invoice is created either way and the
POSTING is refused with a named reason. Unconfigured never means "post it to
something plausible."

⚠️ ONE REVENUE ACCOUNT, AND THE PLATFORM SAYS SO OUT LOUD.
Measured on production 2026-08-19: sunnycrest's chart carries THIRTEEN accounts
in the 5xxx block, every one categorised `cogs` —

    5000 REVENUE · 5010 PRECAST SALES · 5012 REDI-ROCK SALES ·
    5014 ROSETTA SALES · 5020 PRECAST-RESALE · 5110 FUNERAL SALES ·
    5120 FUNERAL-RESALE · 5150/5160 REFUNDS-RETURNS · 5165 FUNERAL REBATES ·
    5170 DAMAGE OR DEFECTIVE RESALE · 5210 FREIGHT · 5410 DISCOUNTS ALLOWED-CASH

The split is by PRODUCT LINE, and the platform cannot honour it: measured the
same day, `products.product_line` is NULL for all 33 products on every
production tenant, and only 7 of 12 issued sunnycrest invoice lines carry a
`product_id` at all. An invoice line has nothing to choose with.

So this is the payroll shape — one platform bucket against many chart accounts —
and the resolution is the same one payroll got: admit it. The tenant configures
ONE account; the split waits for the accountant. Deriving a line's account from
a product line that is universally null would produce a confident wrong answer,
which is worse than a refusal.

⚠️ `platform_category` IS NOT CONSULTED, AND THAT IS DELIBERATE. Every revenue
account on the real chart reads `cogs`; the column is an import-time
classification, not a signal. AR-0 ruled this for the AR account
(`early_payment_discount_service.resolve_ar_account`) and the same ruling holds
here — the tenant's explicit choice, validated at use, or nothing.
"""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Why an invoice could not post. Same vocabulary shape as
# `ar_payment_posting.BLOCK_*` and `reconciliation_gl.BLOCK_*` — the operator's
# fix differs per reason, so the reason is per-leg rather than a single
# "unconfigured".
BLOCK_AR_UNCONFIGURED = "ar_gl_unconfigured"
BLOCK_REVENUE_UNCONFIGURED = "revenue_gl_unconfigured"

_BLOCK_FIX = {
    BLOCK_AR_UNCONFIGURED: (
        "no accounts-receivable GL account is configured for this tenant"
    ),
    BLOCK_REVENUE_UNCONFIGURED: (
        "no sales-revenue GL account is configured for this tenant"
    ),
}


def block_reason_text(reason: str | None) -> str | None:
    """The operator-facing sentence for a block reason, or None.

    A dict lookup rather than `.get(reason, "unknown")`: an unrecognised reason
    is a programming error and should surface as a KeyError in the caller's
    tests, not as the word "unknown" in a report an accountant reads.
    """
    return _BLOCK_FIX[reason] if reason else None


def resolve_invoice_legs(db: Session, company_id: str):
    """``(ar_mapping, revenue_mapping, blocked_reason)`` — the reason is non-None
    iff either mapping is None. Never raises; the caller decides what a failure
    means, and for invoices it means record-anyway-report-the-gap.

    BOTH LEGS ARE `accounting_gl` PURPOSES, unlike the payment path where the
    cash leg lives on the `FinancialAccount`. An invoice touches no bank account,
    so there is no second home to reconcile with — both sides are the tenant's
    stated choice of GL account for a purpose, and both are validated through
    `require_gl_account`, the single definition of "usable GL account" L-2.2
    consolidated to. No third check.

    THE AR LEG IS THE SAME ACCOUNT THE PAYMENT PATH CREDITS. That is the whole
    point of the arc: today AR is credited at payment and never debited at
    invoice, so the control account runs one-directional. Both paths resolving
    `accounting_gl.ar` through the same validator is what makes the two halves
    meet on the same account rather than on two accounts that happen to agree.
    """
    from app.models.company import Company
    from app.services.early_payment_discount_service import (
        ACCOUNTING_GL_SETTINGS_KEY,
    )
    from app.services.reconciliation_gl import validate_gl_account

    company = db.query(Company).filter(Company.id == company_id).first()
    settings = (company.settings if company else None) or {}
    accounting_gl = settings.get(ACCOUNTING_GL_SETTINGS_KEY) or {}
    if not isinstance(accounting_gl, dict):
        # A malformed blob is not a configured tenant. Treated as the AR gap
        # rather than crashing, because the operator's fix is the same panel.
        accounting_gl = {}

    ar_id = accounting_gl.get("ar")
    ar = validate_gl_account(db, company_id, ar_id) if ar_id else None
    if ar is None:
        # AR reported first when BOTH are missing: it is the leg the payment
        # path already depends on, so a tenant fixing it repairs two paths.
        return None, None, BLOCK_AR_UNCONFIGURED

    revenue_id = accounting_gl.get("revenue")
    revenue = validate_gl_account(db, company_id, revenue_id) if revenue_id else None
    if revenue is None:
        return ar, None, BLOCK_REVENUE_UNCONFIGURED

    # ⚠️ THE SAME ACCOUNT ON BOTH LEGS RECORDS NOTHING, and the platform has
    # already met this once — AR-0c's same-account guard fired on real input
    # when testco's AR was pointed at the bank's own contra. Caught here, at
    # resolution, rather than at `create_journal_entry`, so the operator gets a
    # reason naming the panel instead of a balanced-entry error naming nothing
    # they can act on.
    if ar.id == revenue.id:
        return ar, None, BLOCK_REVENUE_UNCONFIGURED

    return ar, revenue, None
