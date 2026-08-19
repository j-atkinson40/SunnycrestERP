"""DEMO-2 — Sunnycrest's accounting demo, posted through the services.

Every accounting path exercisable by a person clicking the live site: AR that
ages, cash that lands six different ways, a bank feed whose exceptions are a
QUEUE rather than a rounding error, and agent work waiting for a decision.

⚠️ POSTS THROUGH SERVICES. NEVER DIRECT ORM CONSTRUCTION.
Every existing seed constructs payment and invoice models directly, so
`post_payment` is never reached and NO journal entry is written: data that
exists and books that do not move. Invisible in review — the seed runs, rows
appear, a page renders a number — and detectable only by asking a question
nobody asks of a seed, *did the ledger move?* The seed-posting ratchet
(`test_seed_posting_ratchet.py`, 4173dc9e) now fails any new construction site
in `scripts/seed_*.py`, so this file routes every guarded model through a
service and constructs only UNGUARDED ones (Customer, CompanyEntity, Product,
Vendor, BankTransaction, AgentJob, AgentAnomaly).

⚠️ TWO CALLS GO TO THE ROUTE LAYER, DELIBERATELY, NOT LAZILY.
`start_run` and `populate_from_feed` are route handlers, not services —
`ReconciliationRun` is constructed in exactly ONE place platform-wide
(`api/routes/reconciliation.py:646`, inside `start_run`), so "post through the
service" is literally impossible for run creation: the reconciliation domain
has no service layer for the run lifecycle. FastAPI's `Depends(...)` are
ordinary default parameter values, so both are callable in plain Python with a
real `User` and `Session`. Recorded in STATE; the alternative — constructing
`ReconciliationRun` here — would be the exact violation this file exists to
avoid, and would need a ratchet allowlist entry to boot.

⚠️ ONE SEED, PHASED. NOT SEVERAL PER DOMAIN.
`run_canonical_seeds.sh` discovers alphabetically, and this work has hard
ordering: config before posting, invoices before payments, payments before
matching. Implicit ordering inside an alphabetical runner is the exact
mechanism that made the MoC fixture chain fail silently — so the ordering is
explicit here, in one file, behind `--phase`.

⚠️ MONEY IS HAND-COMPUTED, NEVER GENERATED.
Every amount is a literal with its arithmetic in a comment. If the seed's
numbers were computed, a matcher bug and a seed bug would be indistinguishable
— the seed would agree with whatever the code did.

⚠️ PHASE 4 HAS NEVER EXECUTED. It is code that compiles and has never met a
database. Phases 0–3, 5 and 6 are dev-verified against testco; phase 4 could not
be, because `populate_from_feed` requires a linked `BankAccount` and testco has
none — fabricating one means fabricating a PlaidItem with an encrypted access
token, i.e. inventing substrate. Its first execution will be against production
sunnycrest, which holds the Plaid sandbox item. The expected-outcome table in
`_FEED_LINES` is what says whether that first run did what it should. Do not
report this seed as "built and tested" until that has happened.

⚠️ PHASES 3 AND 4 ARE COUPLED, AND NEITHER SPEC SAYS SO.
Phase 4's auto-clear count is BOUNDED BY phase 3's payment count — an auto-clear
needs exactly one viable exact match against a real payment record, so N payments
can support at most N auto-clears, fewer once some are consumed by other card
forms. The collision case goes further and imposes a SHAPE on phase 3: it needs
two payments sharing an amount, which "six sub-cases, all distinct" did not
provide (hence the seventh, `collision_twin`). Someone editing either phase in
isolation will break the other silently, and the failure will look like a
matcher bug rather than a seed one.

⚠️ THIS SEED IS NOT ATOMIC, AND MUST NOT BE MADE SO.
The services commit internally, so a mid-run failure leaves earlier phases
PERSISTED — phase 1 survived a phase-2 crash during development, which is how
this was found. Marker-based idempotence is therefore load-bearing rather than
convenient: it is what makes re-running safe instead of duplicative. Do NOT
"improve" this by wrapping the phases in one transaction; the services' own
commits would fight the wrapper, and the failure mode would be a half-written
ledger that looks rolled back.

⚠️ CLEANUP IS SCOPED TO WHAT A RE-SEED REQUIRES, NOT TO WHAT THE FAILURE
TOUCHED. Those are different sets and the second one is the trap. Twice while
building this, cleanup was written against the symptom and was incomplete by
construction:

  * The PAYMENTS had to go, though nothing was wrong with them, because phase 3
    is idempotent on `reference_number` and would SKIP them — and the fix being
    re-seeded was new payment dates. Idempotence working perfectly would have
    reproduced the original failure.
  * The INVOICES had to go, though nothing was wrong with them either, because
    `post_payment` mutated `amount_paid` and `status` on the ones it settled and
    deleting a payment does not undo that. Phase 3 validates against the invoice
    BALANCE, so six fully-paid invoices would have 400'd the re-run.

Neither row was defective. Both blocked the re-seed. The question a cleanup must
answer is "what must not exist for the next run to be honest", not "what did the
bad run write".

IDEMPOTENCE IS BY MARKER PREFIX, not uuid5: `create_customer_payment` mints its
own uuid4 internally, so caller-supplied ids are unavailable once the writes go
through the service layer. Every seeded row carries `DEMO2` in a text field the
service lets the caller set.

Usage::

    python -m scripts.seed_accounting_demo --tenant-slug sunnycrest --phase 0
    python -m scripts.seed_accounting_demo --tenant-slug sunnycrest --phase 1,2,3
    python -m scripts.seed_accounting_demo --tenant-slug sunnycrest --phase all
    python -m scripts.seed_accounting_demo --tenant-slug sunnycrest --cleanup
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.agent import AgentJob
from app.models.agent_anomaly import AgentAnomaly
from app.models.company import Company
from app.models.company_entity import CompanyEntity
from app.models.customer import Customer
from app.models.financial_account import FinancialAccount
from app.models.product import Product
from app.models.user import User
from app.models.vendor import Vendor
from app.schemas.sales import (
    CustomerPaymentCreate,
    InvoiceCreate,
    InvoiceLineCreate,
    PaymentApplicationCreate,
)
from app.schemas.vendor_bill import BillLineCreate, VendorBillCreate
from app.services import reconciliation_gl, sales_service, vendor_bill_service
from app.services.ar_payment_posting import post_payment

#: Stamped into every seeded row, in a field the SERVICE lets a caller set.
#: Cleanup keys on it. Chosen over uuid5 because the service layer owns id
#: minting — see the module docstring.
MARKER = "DEMO2"

#: The seed's "today". Every date below is an offset from this so aging buckets
#: land where they are supposed to no matter when the seed runs.
TODAY = date.today()


def say(msg: str) -> None:
    print(f">>> {msg}")


def die(msg: str) -> None:
    print(f"\n❌ {msg}", file=sys.stderr)
    sys.exit(1)


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 0 — Preflight. Produces nothing. REFUSES.
# ─────────────────────────────────────────────────────────────────────────────

def phase_0_preflight(db: Session, company: Company, actor: User) -> FinancialAccount:
    """Gate the whole seed on the ledger actually being able to post.

    REFUSES BY NAMING WHAT IS MISSING AND WHAT TO DO — the blocked-card
    discipline. "Preconditions not met" tells an operator nothing they can act
    on; the point of a gate is to hand back the next action.
    """
    problems: list[str] = []

    # (a) The keyword map, through its OWN resolver rather than by reading the
    #     settings dict — there are THREE states (mapped / deliberately
    #     unmapped / nobody decided) and only `keyword_gl_with_reason` knows
    #     which is which. Reading the dict here would be a second description
    #     of it, free to drift, which is the bug L-2.1c fixed in the configure
    #     script ("its report read a deliberate null as UNMAPPED").
    from app.services.reconciliation_gl import (
        BLOCK_KEYWORD_GL_INTENTIONAL,
        KEYWORD_CLASSIFICATIONS,
        keyword_gl_with_reason,
    )
    mapped_any = False
    for classification in KEYWORD_CLASSIFICATIONS:
        mapping, reason = keyword_gl_with_reason(db, company, classification)
        if mapping is not None:
            mapped_any = True
        elif reason != BLOCK_KEYWORD_GL_INTENTIONAL:
            problems.append(
                f"keyword '{classification}' is neither mapped nor deliberately "
                f"unmapped (reason={reason}) — set it on /settings/accounts, or "
                f"run: scripts.configure_reconciliation_gl --tenant-slug "
                f"{company.slug} --{classification.replace('_', '-')} <acct#>"
            )
    if not mapped_any:
        problems.append(
            "NO keyword is mapped — at least one must book, or phase 4's "
            "keyword row demonstrates nothing. bank_fee → 8801 is the usual one."
        )

    # (b) A bank account with a contra. Without it `resolve_contra_gl_account`
    #     returns None, the JE has no offsetting leg, and NOTHING books —
    #     phase 4 would produce a statement whose keyword row silently refuses.
    account = (
        db.query(FinancialAccount)
        .filter(
            FinancialAccount.tenant_id == company.id,
            FinancialAccount.is_active.is_(True),
        )
        .order_by(FinancialAccount.created_at)
        .first()
    )
    if account is None:
        problems.append(
            f"no active FinancialAccount on {company.slug} — create one on "
            f"/settings/accounts before seeding."
        )
    elif reconciliation_gl.resolve_contra_gl_account(db, account) is None:
        problems.append(
            f"FinancialAccount {account.account_name!r} has no usable contra GL "
            f"account — set 'GL cash account' in its edit dialog, or run: "
            f"scripts.configure_reconciliation_gl --tenant-slug {company.slug} "
            f"--contra-account {account.account_name!r} --contra <acct#>"
        )

    # (b2) THE PAYMENT LEGS — asked of the resolver `post_payment` ITSELF calls,
    #      not of a list of settings this gate curated. The first version of
    #      this preflight checked the keyword map and the contra, passed, and
    #      then every payment in phase 3 came back `ar_gl_unconfigured`: rows
    #      written, ledger unmoved. The gate had a hole exactly where the file's
    #      whole premise is. A gate that enumerates its own idea of "configured"
    #      will always drift from what the posting path actually requires; one
    #      that asks the posting path cannot.
    from app.services.ar_payment_posting import resolve_payment_legs

    _bank, _ar, legs_reason = resolve_payment_legs(db, company.id)
    if legs_reason is not None:
        problems.append(
            f"payments cannot post ({legs_reason}) — post_payment would record "
            f"every payment and book nothing. BOTH legs must be set: the AR "
            f"account on the tenant (accounting_gl.ar, the E-2 panel on "
            f"/settings/accounts) and the cash account on the bank account "
            f"itself (its 'GL cash account' field)."
        )

    # (c) Migration head. r158 is the floor: the accounting-cadence content this
    #     demo's Map surfaces arrives there.
    from sqlalchemy import text
    head = db.execute(text("SELECT version_num FROM alembic_version")).scalar()
    if not head or head < "r158":
        problems.append(
            f"alembic head is {head!r}, need ≥ r158 — run `alembic upgrade head`."
        )

    # (d) Backlog assertion, SPLIT — because "no parked jobs at all" is a state
    #     the platform cannot legitimately reach and the backlog tool cannot
    #     produce. A month_end_close ALWAYS parks (the close itself is the
    #     decision, and approval writes the PeriodLock), and a job carrying
    #     unresolved anomalies is real work. Demanding zero would leave an
    #     operator looping between a gate and a tool that cannot satisfy it.
    #
    #     So: REFUSE on clearable residue, TOLERATE legitimate work and state it
    #     as a baseline so phase 6's counts stay readable. The residue predicate
    #     is IMPORTED from BaseAgent, not restated — the same frozenset the
    #     runtime uses to decide what may auto-complete.
    from sqlalchemy import func as _func
    from app.services.agents.base_agent import BaseAgent

    parked_q = db.query(AgentJob).filter(
        AgentJob.tenant_id == company.id,
        AgentJob.status == "awaiting_approval",
    )
    residue = parked_q.filter(
        AgentJob.job_type.in_(sorted(BaseAgent.PER_ANOMALY_APPROVAL_JOB_TYPES)),
        _func.coalesce(AgentJob.anomaly_count, 0) == 0,
    ).count()
    legitimate = parked_q.count() - residue

    if residue:
        problems.append(
            f"{residue} parked agent job(s) found nothing and should have "
            f"completed — phase 5's staging would be indistinguishable from "
            f"residue. Clear first: scripts.clear_agent_backlog --tenant-slug "
            f"{company.slug} --execute"
        )
    if legitimate:
        say(f"baseline — {legitimate} legitimately parked job(s) predate this "
            f"seed (real decisions, not residue). Phase 6 counts them separately.")

    if problems:
        print("\n❌ PREFLIGHT REFUSES — the demo cannot post in this state:\n")
        for p in problems:
            print(f"    · {p}")
        print()
        sys.exit(1)

    say(f"preflight OK — account={account.account_name!r} head={head}")
    return account


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 1 — Counterparties + catalogue. All UNGUARDED models: direct is lawful.
# ─────────────────────────────────────────────────────────────────────────────

_CUSTOMERS = [
    # (name, account_number, receives_monthly_statement)
    ("Hopkins Funeral Home", "DEMO2-C001", True),
    ("St. Mary's Cemetery", "DEMO2-C002", True),
    ("Riverside Memorial Chapel", "DEMO2-C003", False),
    ("Fairview Burial Services", "DEMO2-C004", False),
    ("Lakeside Funeral Directors", "DEMO2-C005", False),
]

_VENDORS = [
    ("Northeast Aggregate Supply", "DEMO2-V001", "Net 30"),
    ("Ironclad Rebar & Steel", "DEMO2-V002", "Net 30"),
    ("Auburn Fuel & Fleet", "DEMO2-V003", "Net 15"),
]

_PRODUCTS = [
    # (name, sku, price) — prices are the demo's price list; the invoice
    # arithmetic below quotes them as literals rather than reading them back,
    # so a price edit cannot silently change a hand-proved total.
    ("Monticello Burial Vault", "DEMO2-P001", Decimal("1250.00")),
    ("Continental Burial Vault", "DEMO2-P002", Decimal("1850.00")),
    ("Urn Vault - Standard", "DEMO2-P003", Decimal("425.00")),
    ("Graveside Setup Service", "DEMO2-P004", Decimal("300.00")),
]


def phase_1_counterparties(db: Session, company: Company, actor: User) -> dict:
    made = {"customers": 0, "vendors": 0, "products": 0, "entities": 0}

    for name, acct, monthly in _CUSTOMERS:
        row = db.query(Customer).filter(
            Customer.company_id == company.id, Customer.account_number == acct
        ).one_or_none()
        if row is None:
            row = Customer(
                company_id=company.id, name=name, account_number=acct,
                email=f"ap@{acct.lower()}.example.com", is_active=True,
                receives_monthly_statement=monthly, created_by=actor.id,
            )
            db.add(row)
            made["customers"] += 1
        else:
            row.receives_monthly_statement = monthly

    for name, acct, terms in _VENDORS:
        row = db.query(Vendor).filter(
            Vendor.company_id == company.id, Vendor.account_number == acct
        ).one_or_none()
        if row is None:
            db.add(Vendor(
                company_id=company.id, name=name, account_number=acct,
                payment_terms=terms, is_active=True, created_by=actor.id,
            ))
            made["vendors"] += 1

    for name, sku, price in _PRODUCTS:
        row = db.query(Product).filter(
            Product.company_id == company.id, Product.sku == sku
        ).one_or_none()
        if row is None:
            db.add(Product(
                company_id=company.id, name=name, sku=sku, price=price,
                is_active=True, unit_of_measure="each",
            ))
            made["products"] += 1

    for name, acct, _ in _CUSTOMERS[:3]:
        row = db.query(CompanyEntity).filter(
            CompanyEntity.company_id == company.id, CompanyEntity.name == name
        ).one_or_none()
        if row is None:
            db.add(CompanyEntity(company_id=company.id, name=name, legal_name=name))
            made["entities"] += 1

    db.flush()
    say(f"phase 1 — {made}")
    return made


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 2 — Receivables + payables. Invoice/VendorBill are GUARDED → services.
# ─────────────────────────────────────────────────────────────────────────────
#
# ⚠️ REVENUE DOES NOT POST. `post_invoice_to_ar` moves AR; it books no revenue
# leg. That is the KNOWN GAP, not a seed defect — phase 6 reports the ledger as
# it actually is rather than papering it. A future revenue-posting arc closes it.

#: (customer account, days_ago, [(product sku, qty, unit price)], hand-proved total)
_INVOICES = [
    # Bucket CURRENT (0–30): 3 × 1250.00 = 3750.00; 1 × 425.00 = 425.00
    #                        → 3750.00 + 425.00 = 4175.00
    ("DEMO2-C001", 12, [("DEMO2-P001", 3, "1250.00"), ("DEMO2-P003", 1, "425.00")],
     Decimal("4175.00")),
    # Bucket CURRENT: 1 × 1850.00 = 1850.00; 1 × 300.00 = 300.00 → 2150.00
    ("DEMO2-C003", 8, [("DEMO2-P002", 1, "1850.00"), ("DEMO2-P004", 1, "300.00")],
     Decimal("2150.00")),
    # Bucket 31–60: 2 × 1850.00 = 3700.00; 3 × 415.481 is NOT used — the EPD
    # case needs an odd total, so: 1 × 1250.00 = 1250.00 plus 1 × 3696.43
    # bespoke line → 1250.00 + 3696.43 = 4946.43. Chosen because 2% of it is
    # 98.9286 → 98.93, the W-2 EPD figure, so the ranked-card band is exercised
    # at the exact width AMOUNT_BAND_PCT was derived from.
    ("DEMO2-C002", 45, [("DEMO2-P001", 1, "1250.00"), (None, 1, "3696.43")],
     Decimal("4946.43")),
    # Bucket 31–60: 1 × 1500.00 → 1500.00 (the overpayment target)
    ("DEMO2-C004", 52, [(None, 1, "1500.00")], Decimal("1500.00")),
    # Bucket 61–90: 1 × 2300.00 → 2300.00 (the EPD-out-of-window target)
    ("DEMO2-C005", 75, [(None, 1, "2300.00")], Decimal("2300.00")),
    # Bucket 61–90: 2 × 425.00 = 850.00; 1 × 130.00 = 130.00 → 980.00 (to void)
    ("DEMO2-C003", 82, [("DEMO2-P003", 2, "425.00"), (None, 1, "130.00")],
     Decimal("980.00")),
    # Bucket 90+: 1 × 1120.00 → 1120.00 (the returned-payment target)
    ("DEMO2-C004", 104, [(None, 1, "1120.00")], Decimal("1120.00")),
    # Bucket 90+: 3 × 1250.00 = 3750.00 → 3750.00 (stays open, ages)
    ("DEMO2-C005", 121, [("DEMO2-P001", 3, "1250.00")], Decimal("3750.00")),
]

#: (vendor account, days_ago, [(description, qty, unit cost)], hand-proved total)
_BILLS = [
    # 40 × 62.50 = 2500.00
    ("DEMO2-V001", 20, [("Concrete aggregate, 40 ton", 40, "62.50")], Decimal("2500.00")),
    # 12 × 145.00 = 1740.00
    ("DEMO2-V002", 34, [("Rebar bundle, #4", 12, "145.00")], Decimal("1740.00")),
    # 380 × 3.95 = 1501.00
    ("DEMO2-V003", 9, [("Diesel, gallons", 380, "3.95")], Decimal("1501.00")),
]


def _customer_by_acct(db: Session, company: Company, acct: str) -> Customer:
    return db.query(Customer).filter(
        Customer.company_id == company.id, Customer.account_number == acct
    ).one()


def _product_by_sku(db: Session, company: Company, sku: str) -> Product:
    return db.query(Product).filter(
        Product.company_id == company.id, Product.sku == sku
    ).one()


def phase_2_receivables(db: Session, company: Company, actor: User) -> dict:
    from app.models.invoice import Invoice
    from app.models.vendor_bill import VendorBill

    made = {"invoices": 0, "bills": 0, "skipped": 0}

    for acct, days_ago, lines, expected_total in _INVOICES:
        note = f"{MARKER} invoice for {acct} d-{days_ago}"
        if db.query(Invoice).filter(
            Invoice.company_id == company.id, Invoice.notes == note
        ).first():
            made["skipped"] += 1
            continue

        customer = _customer_by_acct(db, company, acct)
        inv_date = datetime.combine(TODAY - timedelta(days=days_ago), datetime.min.time())
        line_models = []
        for sku, qty, unit in lines:
            product = _product_by_sku(db, company, sku) if sku else None
            line_models.append(InvoiceLineCreate(
                product_id=product.id if product else None,
                description=product.name if product else "Services rendered",
                quantity=Decimal(qty), unit_price=Decimal(unit),
            ))
        payload = InvoiceCreate(
            customer_id=customer.id,
            invoice_date=inv_date,
            due_date=inv_date + timedelta(days=30),
            payment_terms="Net 30",
            # Tax deliberately 0: every total above is hand-proved, and a tax
            # rate would put a rounding step between the literal and the row
            # that the comment could not show.
            tax_rate=Decimal("0.00"),
            notes=note,
            lines=line_models,
        )
        invoice = sales_service.create_invoice(db, company.id, actor.id, payload)
        if Decimal(str(invoice.total)) != expected_total:
            die(f"invoice total {invoice.total} != hand-proved {expected_total} "
                f"for {acct} d-{days_ago} — the seed and the service disagree.")
        # `sent`, not draft: create_invoice mints drafts, and a draft is not an
        # open receivable — the matcher's _OPEN_INVOICE_STATUSES excludes it, so
        # a draft invoice would be invisible to phase 4's candidate pool.
        invoice.status = "sent"
        sales_service.post_invoice_to_ar(db, company.id, invoice)
        made["invoices"] += 1

    for acct, days_ago, lines, expected_total in _BILLS:
        marker_ref = f"{MARKER}-{acct}-{days_ago}"
        if db.query(VendorBill).filter(
            VendorBill.company_id == company.id,
            VendorBill.vendor_invoice_number == marker_ref,
        ).first():
            made["skipped"] += 1
            continue

        vendor = db.query(Vendor).filter(
            Vendor.company_id == company.id, Vendor.account_number == acct
        ).one()
        bill_date = (TODAY - timedelta(days=days_ago)).isoformat()
        payload = VendorBillCreate(
            vendor_id=vendor.id,
            vendor_invoice_number=marker_ref,
            bill_date=bill_date,
            subtotal=expected_total,
            tax_amount=Decimal("0.00"),
            total=expected_total,
            notes=f"{MARKER} vendor bill",
            # `amount` is the LINE TOTAL and is required. Each bill above has a
            # single line, so its amount IS the hand-proved bill total — stated
            # as the same literal rather than multiplied here, so the arithmetic
            # lives in one place (the comment beside the tuple) and a typo shows
            # up as a mismatch instead of agreeing with itself.
            lines=[BillLineCreate(
                description=desc, quantity=Decimal(qty),
                unit_cost=Decimal(unit), amount=expected_total,
            ) for desc, qty, unit in lines],
        )
        vendor_bill_service.create_vendor_bill(db, payload, company.id, actor.id)
        made["bills"] += 1

    db.flush()
    say(f"phase 2 — {made}  (revenue does NOT post; AR moves. Known gap.)")
    return made


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 3 — Cash received. Six sub-cases, every one through the service pair.
# ─────────────────────────────────────────────────────────────────────────────
#
# THE LAST TWO ARE SEEDED POSTED AND LEFT ALONE. The void and the NSF return are
# the demo's job to perform — a person should watch the ledger unwind, which is
# the whole point of demonstrating them. Pre-unwinding here would leave two rows
# in a terminal state and nothing to show.

#: ⚠️ `days_ago` IS PHASE 4's CONSTRAINT, NOT A FLAVOUR CHOICE. An auto-clear
#: needs its payment within `DATE_WINDOW_DAYS` (5) of the statement line, and
#: phase 4 dates its matched lines at the END of the feed window — which is
#: `TODAY - 1`. So every value below is ≤ 4, putting each payment within four
#: days of that line with a day of margin.
#:
#: THE FIRST PRODUCTION RUN FAILED EXACTLY HERE. The amounts were designed and
#: the dates were not: feed dates came from the window, payment dates from these
#: offsets, and nothing made them agree. Gaps of 6, 9 and 20 days meant NO line
#: had a viable exact candidate — auto=1 against an expected 4, and suggested=0.
#: The relationship is one-directional now (payments are dated to suit the feed,
#: which is dated to suit the window) rather than two independent computations
#: that have to coincide.
#:
#: (label, invoice matched by note-suffix, days_ago, amount, applied, method)
_PAYMENTS = [
    # 1. NORMAL — settles 4175.00 exactly. 4175.00 applied, 0.00 unapplied.
    ("normal", "DEMO2-C001 d-12", 4, Decimal("4175.00"), Decimal("4175.00"), "check"),
    # 2. EPD IN WINDOW — 2/10 net 30 against 4946.43.
    #    discount = 4946.43 × 0.02 = 98.9286 → 98.93
    #    paid     = 4946.43 − 98.93 = 4847.50
    #    The 98.93 short-pay is 2.00% — inside AMOUNT_BAND_PCT (3%), so phase 4
    #    can surface this as a ranked card at BAND_MAX_SCORE rather than clearing.
    ("epd_in_window", "DEMO2-C002 d-45", 4, Decimal("4847.50"), Decimal("4847.50"), "ach"),
    # 3. EPD OUT OF WINDOW — 2300.00 invoice, paid in full because the discount
    #    window closed. No short-pay: 2300.00 − 0.00 = 2300.00.
    ("epd_out_of_window", "DEMO2-C005 d-75", 3, Decimal("2300.00"), Decimal("2300.00"), "check"),
    # 4. OVERPAYMENT — 1500.00 invoice, 1750.00 received.
    #    unapplied = 1750.00 − 1500.00 = 250.00 → the customer's credit pocket.
    ("overpayment", "DEMO2-C004 d-52", 2, Decimal("1750.00"), Decimal("1500.00"), "check"),
    # 5. TO VOID — 980.00, posted. LEFT POSTED for the demo to void.
    ("to_void", "DEMO2-C003 d-82", 3, Decimal("980.00"), Decimal("980.00"), "check"),
    # 6. TO RETURN — 1120.00, posted. LEFT POSTED for the demo to NSF-return.
    ("to_return", "DEMO2-C004 d-104", 2, Decimal("1120.00"), Decimal("1120.00"), "check"),
    # 7. COLLISION TWIN — 1750.00, the SAME amount as `overpayment` above, and
    #    that duplication is its entire purpose. Phase 4 seeds one statement
    #    line at 1750.00 which therefore has TWO viable exact candidates, and
    #    `run_matching` only auto-commits when `len(viable_exact) == 1` — so the
    #    line surfaces as a ranked card with genuine ambiguity instead of
    #    clearing. Named rather than filler so the pair's purpose is visible
    #    HERE, at the seed, rather than inferable from phase 4.
    #    Applied 1750.00 against the open 2150.00 invoice → leaves 400.00 open.
    ("collision_twin", "DEMO2-C003 d-8", 2, Decimal("1750.00"), Decimal("1750.00"), "ach"),
]


def phase_3_cash(db: Session, company: Company, actor: User) -> dict:
    from app.models.customer_payment import CustomerPayment
    from app.models.invoice import Invoice

    made = {"payments": 0, "posted": 0, "unposted": 0, "skipped": 0}

    for label, inv_suffix, days_ago, amount, applied, method in _PAYMENTS:
        ref = f"{MARKER}-PAY-{label}"
        if db.query(CustomerPayment).filter(
            CustomerPayment.company_id == company.id,
            CustomerPayment.reference_number == ref,
        ).first():
            made["skipped"] += 1
            continue

        invoice = db.query(Invoice).filter(
            Invoice.company_id == company.id,
            Invoice.notes == f"{MARKER} invoice for {inv_suffix}",
        ).one()
        payload = CustomerPaymentCreate(
            customer_id=invoice.customer_id,
            payment_date=datetime.combine(
                TODAY - timedelta(days=days_ago), datetime.min.time()
            ),
            total_amount=amount,
            payment_method=method,
            reference_number=ref,
            notes=f"{MARKER} {label}",
            applications=[PaymentApplicationCreate(
                invoice_id=invoice.id, amount_applied=applied,
            )],
        )
        payment = sales_service.create_customer_payment(db, company.id, actor.id, payload)
        # THE SECOND CALL IS THE POINT. create_customer_payment records; only
        # post_payment books Dr bank / Cr AR. A seed that stopped at the first
        # would leave the ledger unmoved — the exact defect the ratchet exists
        # to prevent, and it would look complete from every page in the app.
        entry = post_payment(db, company_id=company.id, payment=payment, user_id=actor.id)
        made["payments"] += 1
        made["posted" if entry is not None else "unposted"] += 1

    db.flush()
    say(f"phase 3 — {made}")
    if made["unposted"]:
        say(f"  ⚠️ {made['unposted']} payment(s) recorded but NOT posted — "
            f"post_payment returned None (a configuration gap it reports rather "
            f"than raises). Phase 6 will show this as the AR-2 difference.")
    return made


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 4 — Bank feed + reconciliation. NOT BUILT PENDING RATIO SIGN-OFF.
# ─────────────────────────────────────────────────────────────────────────────

#: THE POPULATION IS DESIGNED, NOT INCIDENTAL — every line is here to produce a
#: specific card form, and the form each one produces is a consequence of the
#: matcher's OWN rules, read rather than assumed:
#:
#:   auto-clear   `len(viable_exact) == 1` and the date within DATE_WINDOW_DAYS
#:   ranked       a candidate inside AMOUNT_BAND_PCT (3%), capped at
#:                BAND_MAX_SCORE (0.85) so it can never auto-commit
#:   collision    TWO viable exact candidates → the `== 1` test fails → ranked
#:   coding       no candidate within the band of anything
#:   keyword      the description ladder, before any candidate search
#:
#: ⚠️ `AUTO_COMMIT_THRESHOLD` IS A DECOY. It is defined in reconciliation_service
#: and referenced NOWHERE — the real rule is `len(viable_exact) == 1` with
#: reference-matching as the fallback. A collision line designed against the
#: constant would auto-clear and the ambiguity would never appear.
#:
#: W-2 ended at 95.8% auto-match with an empty workspace. That is the failure
#: mode this table exists to avoid: the queue is what the demo teaches.
#:
#: (label, days_before_statement, amount, description, reference_number)
_FEED_LINES = [
    # ── 3 AUTO-CLEAR — exact, unique, recent. Dated EARLIEST so they claim
    #    their payments before the band lines below are scored; the matcher
    #    walks in sort_order, and populate_from_feed sorts by date.
    ("auto_normal",   18, Decimal("4175.00"),  "DEPOSIT HOPKINS FUNERAL HOME", "DEMO2-BF-01"),
    ("auto_epd_out",  17, Decimal("2300.00"),  "DEPOSIT LAKESIDE FUNERAL",     "DEMO2-BF-02"),
    ("auto_to_void",  16, Decimal("980.00"),   "DEPOSIT RIVERSIDE MEMORIAL",   "DEMO2-BF-03"),

    # ── 1 COLLISION — matches BOTH `overpayment` and `collision_twin`, which
    #    are both 1750.00. reference_number is DELIBERATELY None: with a
    #    reference set, the `elif txn.reference_number` fallback would find one
    #    of the two by reference and auto-accept it at 0.97, and the ambiguity
    #    this line exists to demonstrate would never reach the queue.
    ("collision",     15, Decimal("1750.00"),  "DEPOSIT ACH BATCH",            None),

    # ── 3 RANKED vs unclaimed payments — 2% below, inside the 3% band.
    #    4847.50 − 97.50 = 4750.00   (97.50 / 4847.50 = 2.01%)
    ("band_pay_a",    14, Decimal("4750.00"),  "DEPOSIT ST MARYS CEMETERY",    "DEMO2-BF-05"),
    #    1750.00 − 35.00 = 1715.00   (35.00 / 1750.00 = 2.00%)
    #    ⚠️ WAS "DEPOSIT ACH RETURNED ITEM ADJ" AND THAT BROKE IT. "RETURNED" is
    #    on the nsf rung of the keyword ladder, the ladder runs BEFORE candidate
    #    matching, so the line was classified and blocked rather than ever being
    #    scored against an amount. A description written for plausibility
    #    removed a card form from the demo, and the symptom — a band candidate
    #    that silently never appears — looks like a matcher bug. Guarded below.
    ("band_pay_b",    13, Decimal("1715.00"),  "DEPOSIT ACH BATCH SETTLEMENT", "DEMO2-BF-06"),
    #    1120.00 − 22.40 = 1097.60   (22.40 / 1120.00 = 2.00%)
    ("band_pay_c",    12, Decimal("1097.60"),  "DEPOSIT FAIRVIEW BURIAL",      "DEMO2-BF-07"),

    # ── 1 RANKED vs an open invoice — the EPD-shaped case, the exact width
    #    AMOUNT_BAND_PCT was derived from.
    #    3750.00 − 75.00 = 3675.00   (75.00 / 3750.00 = 2.00%)
    ("band_invoice",  11, Decimal("3675.00"),  "DEPOSIT LAKESIDE 2PCT",        "DEMO2-BF-08"),

    # ── 10 CODING — no candidate within 3% of any payment or open invoice.
    #    Checked against the phase-3 amounts (4175.00 4847.50 2300.00 1750.00
    #    980.00 1120.00) and the open invoice balances; nearest neighbour on
    #    every line below is >3% away, so each produces zero candidates.
    ("coding_01",     10, Decimal("312.45"),   "DEPOSIT COUNTER CREDIT",       "DEMO2-BF-09"),
    ("coding_02",      9, Decimal("-87.20"),   "OFFICE SUPPLY CO",             "DEMO2-BF-10"),
    ("coding_03",      9, Decimal("-645.10"),  "AUBURN UTILITIES",             "DEMO2-BF-11"),
    ("coding_04",      8, Decimal("-1289.33"), "NORTHEAST AGGREGATE",          "DEMO2-BF-12"),
    ("coding_05",      8, Decimal("-55.00"),   "STATE FILING FEE",             "DEMO2-BF-13"),
    ("coding_06",      7, Decimal("-2765.80"), "EQUIPMENT LEASE",              "DEMO2-BF-14"),
    ("coding_07",      7, Decimal("199.99"),   "REFUND VENDOR CREDIT",         "DEMO2-BF-15"),
    ("coding_08",      6, Decimal("-431.07"),  "FLEET INSURANCE",              "DEMO2-BF-16"),
    ("coding_09",      6, Decimal("-158.62"),  "PHONE AND INTERNET",           "DEMO2-BF-17"),
    ("coding_10",      5, Decimal("-3402.15"), "IRONCLAD REBAR STEEL",         "DEMO2-BF-18"),

    # ── 1 KEYWORD THAT BOOKS — `SERVICE CHARGE` hits the bank_fee rung at 0.90.
    #    Resolves both legs, books a balanced two-legged DRAFT journal entry,
    #    and clears. Negative: money out.
    ("keyword_fee",    4, Decimal("-38.50"),   "MONTHLY SERVICE CHARGE",       "DEMO2-BF-19"),

    # ── 1 KEYWORD THAT REFUSES — `PAYROLL` hits the payroll rung, which is
    #    DELIBERATELY UNMAPPED on this tenant. Booking is the licence to clear,
    #    so it books nothing and stays unmatched with an exception carrying
    #    `keyword_gl_intentional`. THE ONLY CARD IN THE QUEUE THAT IS A POSITIVE
    #    STATE — everything else is something the system could not resolve; this
    #    is something it deliberately will not, and a person books it.
    ("keyword_payroll", 3, Decimal("-4210.00"), "GUSTO PAYROLL",               "DEMO2-BF-20"),
]

#: What the run MUST produce, COUNTED FROM `reconciliation_match_candidates`
#: RATHER THAN THE RUN SUMMARY.
#:
#: ⚠️ THE FIRST VERSION ASSERTED ON THE SUMMARY AND COULD NOT SEE ITS OWN
#: SUBJECT. It checked lines / auto_cleared / needs_human, and `needs_human`
#: folded ranked and coding cards together — so a queue of twenty coding cards
#: and a queue with the designed mix produced the SAME number. It passed a run
#: whose ranked cards were the open question. Worse, `suggested_count` is
#: hardcoded to 0 in `reconciliation_service` (vestigial after L-2, kept so the
#: API shape does not churn), so reading it as evidence about band candidates —
#: which I did, twice — is reading a constant.
#:
#: The card form derives from CANDIDATE PRESENCE (`financial_account.py:150`:
#: "card form derives from candidate presence at display"), so that is what the
#: table counts. `ranked` is the number that would have failed the first run and
#: passes this one, which is the entire point of having it.
_EXPECTED = {
    "lines": 20,
    "cleared": 4,   # 3 exact matches + the SERVICE CHARGE that books and clears
    "ranked": 5,    # 1 collision (2 candidates) + 4 band (1715 also draws 2)
    "coding": 10,   # unmatched with NO candidate — nothing to rank
    "blocked": 1,   # GUSTO PAYROLL: keyword_gl_intentional, books nothing
}


def phase_4_bank_feed(db: Session, company: Company, actor: User, account) -> dict:
    """Bank feed → run → populate → match. THE FIRST EXECUTION IS THE TEST.

    TWO ROUTE CALLS, DELIBERATE. `start_run` and `populate_from_feed` are route
    handlers; `ReconciliationRun` is constructed in exactly one place platform-
    wide and it is inside `start_run`, so there is no service to call. See the
    module docstring.
    """
    from app.api.routes.reconciliation import (
        StartRunRequest, populate_from_feed, start_run,
    )
    from app.models.plaid import BankAccount, BankTransaction

    linked = (
        db.query(BankAccount)
        .filter(
            BankAccount.financial_account_id == account.id,
            BankAccount.tenant_id == company.id,
            BankAccount.is_active.is_(True),
        )
        .all()
    )
    if not linked:
        die(
            f"no linked BankAccount for {account.account_name!r} — "
            f"`populate_from_feed` requires one and this seed will NOT fabricate "
            f"a PlaidItem to get it. Link a bank account on the connection card, "
            f"or run this phase against a tenant that has one (production "
            f"sunnycrest holds the Plaid sandbox item)."
        )
    feed_account = linked[0]

    # ⚠️ THE KEYWORD LADDER RUNS BEFORE CANDIDATE MATCHING, so a description
    # decides whether a line is ever scored against an amount at all. Only the
    # two lines that are SUPPOSED to be keyword rows may match a rung; any other
    # match silently removes a card form from the demo and presents as a matcher
    # bug. Read from `_KEYWORD_LADDER` rather than restated, so a rung added
    # later is caught here instead of the next time someone writes a plausible
    # bank description.
    from app.services.reconciliation_service import _KEYWORD_LADDER

    for label, _o, _amt, description, _r in _FEED_LINES:
        hit = next(
            (c for c, _conf, kws in _KEYWORD_LADDER
             if any(kw in description.upper() for kw in kws)),
            None,
        )
        intended = label.startswith("keyword_")
        if bool(hit) != intended:
            die(
                f"feed line {label!r} — description {description!r} "
                + (f"matches the {hit!r} keyword rung but is not a keyword line; "
                   f"it would be classified and blocked before its amount is "
                   f"ever compared."
                   if hit else
                   "is a keyword line but matches no rung, so it will fall "
                   "through to candidate matching instead of booking.")
            )

    # ⚠️ THE WINDOW MUST EXCLUDE THE PRE-EXISTING FEED, and a fixed 30-day
    # lookback does NOT. `populate_from_feed` pulls from EVERY linked bank
    # account within [period_start, statement_date] — production's Plaid sandbox
    # item holds 16 rows dated 2026-07-08..07-28 across six linked accounts, and
    # a 30-day window swallows ~13 of them. The run would materialise ~33 lines,
    # `_EXPECTED` would mismatch, and the mismatch would read as the matcher
    # disagreeing rather than the window overlapping. Plaid's rows keep their
    # OWN run so ingest stays separately demonstrable — that is the hybrid
    # design, and this is what makes it true rather than merely stated.
    from sqlalchemy import func as _f
    from app.models.plaid import BankTransaction as _BT

    statement_date = TODAY - timedelta(days=1)
    last_existing = (
        db.query(_f.max(_BT.transaction_date))
        .filter(
            _BT.tenant_id == company.id,
            _BT.bank_account_id.in_([a.id for a in linked]),
            ~_BT.plaid_transaction_id.like(f"{MARKER}-%"),
        )
        .scalar()
    )
    period_start = statement_date - timedelta(days=30)
    if last_existing is not None and last_existing >= period_start:
        period_start = last_existing + timedelta(days=1)
    window_days = (statement_date - period_start).days + 1
    if window_days < len(_FEED_LINES) // 2:
        die(
            f"the feed window is only {window_days} day(s) "
            f"({period_start}..{statement_date}) because existing feed rows run "
            f"to {last_existing} — too tight to date {len(_FEED_LINES)} demo "
            f"lines distinctly. Widen by seeding against a later statement_date."
        )

    # PLAID HYBRID — the existing feed rows keep their own runs so ingest stays
    # separately demonstrable; these are the lines that carry the demo, marked
    # so cleanup can find them and so nobody mistakes them for Plaid's.
    made = 0
    for i, (label, _authored_offset, amount, description, _ref) in enumerate(_FEED_LINES):
        # DATE DERIVED FROM POSITION, not from the tuple's offset field. The
        # matcher walks in sort_order, populate_from_feed sorts by date, and the
        # auto-clear lines must claim their payments BEFORE the band lines are
        # scored — so list order is the thing that matters, and deriving the date
        # from the index makes that guaranteed rather than dependent on 20
        # hand-tuned offsets still fitting a window whose width now varies with
        # the existing feed. The tuple's offset survives as authored intent.
        plaid_id = f"{MARKER}-TXN-{label}"
        if db.query(BankTransaction).filter(
            BankTransaction.tenant_id == company.id,
            BankTransaction.plaid_transaction_id == plaid_id,
        ).first():
            continue
        db.add(BankTransaction(
            tenant_id=company.id,
            bank_account_id=feed_account.id,
            plaid_transaction_id=plaid_id,
            amount=amount,
            # DATE DERIVED FROM ROLE. A line that must MATCH a payment sits AT
            # the statement date, because phase 3 dates those payments ≤4 days
            # earlier — so the pair is inside DATE_WINDOW_DAYS by construction
            # rather than by two independent calculations happening to agree.
            # That agreement is exactly what failed on the first production run.
            # Lines with nothing to match spread across the window so the
            # statement reads like a month rather than a single day.
            transaction_date=(
                statement_date
                if label.startswith(("auto_", "band_", "collision"))
                else period_start + timedelta(days=min(i, window_days - 1))
            ),
            description=description,
            # POSTED and not retracted, or populate_from_feed filters it out.
            is_pending=False,
            removed_at=None,
        ))
        made += 1
    db.flush()

    # Closing balance is not load-bearing for matching — the difference is what
    # the close gate reads, and this demo leaves it non-zero on purpose so the
    # operator sees an unreconciled figure rather than a solved one.
    started = start_run(
        body=StartRunRequest(
            account_id=account.id,
            statement_date=statement_date.isoformat(),
            statement_closing_balance=0.0,
            period_start=period_start.isoformat(),
        ),
        current_user=actor, db=db,
    )
    run_id = started["id"]
    populated = populate_from_feed(run_id=run_id, current_user=actor, db=db)

    from app.models.financial_account import ReconciliationRun
    from app.services.reconciliation_service import run_matching

    run = db.query(ReconciliationRun).filter(ReconciliationRun.id == run_id).one()
    result = run_matching(db, run, company.id)
    db.flush()

    say(f"phase 4 — seeded {made} feed rows, populated {populated['populated']}, "
        f"matched {result}")

    # POST-HOC, AGAINST THE DATABASE. This cannot be a static test: the card
    # forms only exist once a run has scored, so the assertion lives where the
    # run reports. Counted from the candidate table because that is what the
    # display derives the card form from — the run summary carries two vestigial
    # fields and cannot answer this.
    from sqlalchemy import text as _text

    shape = db.execute(_text("""
        SELECT
          count(*) FILTER (WHERE t.match_status = 'auto_cleared'
                              OR t.journal_entry_id IS NOT NULL)          AS cleared,
          count(*) FILTER (WHERE t.match_status = 'unmatched' AND c.n > 0) AS ranked,
          count(*) FILTER (WHERE t.match_status = 'unmatched' AND c.n = 0
                              AND e.blocked IS NULL)                       AS coding,
          count(*) FILTER (WHERE e.blocked IS NOT NULL)                    AS blocked
        FROM reconciliation_transactions t
        LEFT JOIN LATERAL (
            SELECT count(*) AS n FROM reconciliation_match_candidates mc
            WHERE mc.reconciliation_transaction_id = t.id
        ) c ON true
        LEFT JOIN LATERAL (
            SELECT max(blocked_reason) AS blocked FROM reconciliation_exceptions x
            WHERE x.reconciliation_transaction_id = t.id
              AND x.blocked_reason LIKE 'keyword_gl%'
        ) e ON true
        WHERE t.reconciliation_run_id = :r
    """), {"r": run_id}).one()

    actual = {
        "lines": populated["populated"], "cleared": shape.cleared,
        "ranked": shape.ranked, "coding": shape.coding, "blocked": shape.blocked,
    }
    say(f"  shape — {actual}")
    if actual != _EXPECTED:
        diff = {k: (v, actual[k]) for k, v in _EXPECTED.items() if actual[k] != v}
        say(f"  ⚠️ EXPECTED {_EXPECTED} — GOT {actual}. Differs on "
            f"{ {k: f'want {w}, got {g}' for k, (w, g) in diff.items()} }. The "
            f"population and the matcher disagree; one of them is wrong and the "
            f"table is what says so.")
    return {"seeded": made, **result, **actual}


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 5 — Agent staging. AgentJob/AgentAnomaly are UNGUARDED → direct.
# ─────────────────────────────────────────────────────────────────────────────

_ANOMALIES = [
    # (job_type, severity, anomaly_type, description, amount)
    ("cash_receipts_matching", "warning", "payment_possible_match",
     "Payment of $2,150.00 from Riverside Memorial Chapel may match Invoice "
     "balance $2,150.00. Confirm match.", Decimal("2150.00")),
    ("cash_receipts_matching", "info", "payment_unmatched_recent",
     "Payment of $1,750.00 from Fairview Burial Services has $250.00 unapplied "
     "sitting in the credit pocket.", Decimal("250.00")),
    ("ar_collections", "warning", "invoice_overdue",
     "Lakeside Funeral Directors invoice is 121 days overdue at $3,750.00.",
     Decimal("3750.00")),
    ("ar_collections", "critical", "invoice_severely_overdue",
     "Fairview Burial Services invoice is 104 days overdue at $1,120.00.",
     Decimal("1120.00")),
    ("expense_categorization", "info", "uncategorized_expense",
     "Auburn Fuel & Fleet bill of $1,501.00 has no expense category.",
     Decimal("1501.00")),
]


def phase_5_agents(db: Session, company: Company, actor: User) -> dict:
    made = {"jobs": 0, "anomalies": 0, "skipped": 0}
    now = datetime.now(timezone.utc)

    # One job per type carrying its anomalies, plus a month_end_close parked for
    # approval. month_end_close is the PER-JOB shape: the close ITSELF is the
    # decision and approval writes the PeriodLock, which is why it always parks
    # however quiet the run — see BaseAgent.PER_ANOMALY_APPROVAL_JOB_TYPES.
    by_type: dict[str, AgentJob] = {}
    for job_type, *_ in _ANOMALIES:
        if job_type in by_type:
            continue
        existing = db.query(AgentJob).filter(
            AgentJob.tenant_id == company.id,
            AgentJob.job_type == job_type,
            AgentJob.report_pdf_path == f"{MARKER}",
        ).first()
        if existing:
            by_type[job_type] = existing
            made["skipped"] += 1
            continue
        job = AgentJob(
            tenant_id=company.id, job_type=job_type, status="awaiting_approval",
            trigger_type="manual", triggered_by=actor.id, dry_run=False,
            anomaly_count=0, started_at=now, created_at=now,
            # No text marker column exists on agent_jobs; report_pdf_path is the
            # one free-text field the model has that nothing else populates for
            # a job that produced no PDF. Cleanup keys on it.
            report_pdf_path=MARKER,
        )
        db.add(job)
        db.flush()
        by_type[job_type] = job
        made["jobs"] += 1

    for job_type, severity, anomaly_type, description, amount in _ANOMALIES:
        job = by_type[job_type]
        if db.query(AgentAnomaly).filter(
            AgentAnomaly.agent_job_id == job.id,
            AgentAnomaly.description == description,
        ).first():
            made["skipped"] += 1
            continue
        db.add(AgentAnomaly(
            agent_job_id=job.id, severity=severity, anomaly_type=anomaly_type,
            description=description, amount=amount, resolved=False,
        ))
        job.anomaly_count = (job.anomaly_count or 0) + 1
        made["anomalies"] += 1

    if not db.query(AgentJob).filter(
        AgentJob.tenant_id == company.id,
        AgentJob.job_type == "month_end_close",
        AgentJob.report_pdf_path == MARKER,
    ).first():
        db.add(AgentJob(
            tenant_id=company.id, job_type="month_end_close",
            status="awaiting_approval", trigger_type="manual",
            triggered_by=actor.id, dry_run=False, anomaly_count=0,
            started_at=now, created_at=now, report_pdf_path=MARKER,
        ))
        made["jobs"] += 1

    db.flush()
    say(f"phase 5 — {made}")
    return made


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 6 — Verify. A REPORT, no rows. The report IS the artifact.
# ─────────────────────────────────────────────────────────────────────────────

def phase_6_verify(db: Session, company: Company) -> dict:
    from sqlalchemy import func
    from app.models.customer_payment import CustomerPayment
    from app.models.invoice import Invoice
    from app.models.journal_entry import JournalEntry

    inv_q = db.query(Invoice).filter(Invoice.company_id == company.id)
    buckets = {"current": 0, "31-60": 0, "61-90": 0, "90+": 0}
    outstanding = Decimal("0.00")
    for inv in inv_q.filter(Invoice.status.in_(("sent", "partial", "overdue"))).all():
        age = (TODAY - inv.invoice_date.date()
               if hasattr(inv.invoice_date, "date") else TODAY - inv.invoice_date).days
        key = ("current" if age <= 30 else "31-60" if age <= 60
               else "61-90" if age <= 90 else "90+")
        buckets[key] += 1
        outstanding += Decimal(str(inv.total)) - Decimal(str(inv.amount_paid or 0))

    cash_in = db.query(func.coalesce(func.sum(CustomerPayment.total_amount), 0)).filter(
        CustomerPayment.company_id == company.id,
        CustomerPayment.reference_number.like(f"{MARKER}-%"),
    ).scalar()
    # `tenant_id`, NOT `company_id` — the codebase carries both conventions and
    # journal_entries is on the tenant_id side. Verified against the model, not
    # assumed; the two-convention hazard is documented in CLAUDE.md and it cost
    # a run here.
    je_count = db.query(func.count(JournalEntry.id)).filter(
        JournalEntry.tenant_id == company.id
    ).scalar()

    # AR-2's invariant: cash movement equals platform_cleared_balance, or the
    # gap equals the sum of reported unposted-payment anomalies. Reported, not
    # asserted — an unposted payment is a CONFIGURATION fact the seed should
    # surface, not a crash.
    unposted = db.query(func.count(AgentAnomaly.id)).join(
        AgentJob, AgentAnomaly.agent_job_id == AgentJob.id
    ).filter(
        AgentJob.tenant_id == company.id,
        AgentAnomaly.anomaly_type == "payment_not_posted",
        AgentAnomaly.resolved.is_(False),
    ).scalar()

    print("\n" + "=" * 68)
    print(f"DEMO-2 VERIFY — {company.name} ({company.slug})")
    print("=" * 68)
    print(f"  invoices by age   current={buckets['current']}  31-60={buckets['31-60']}  "
          f"61-90={buckets['61-90']}  90+={buckets['90+']}")
    print(f"  AR outstanding    ${outstanding:,.2f}")
    print(f"  demo cash in      ${Decimal(str(cash_in)):,.2f}")
    print(f"  journal entries   {je_count}")
    print(f"  unposted-payment anomalies  {unposted}")
    print(f"  bank feed         (phase 4 pending ratio sign-off)")
    print("=" * 68)
    if je_count == 0:
        print("  ⚠️ ZERO journal entries — the ledger did not move. Something\n"
              "     recorded rows without posting them; that is the exact defect\n"
              "     the seed-posting ratchet exists to prevent.")
    print()
    return {"buckets": buckets, "outstanding": outstanding, "journal_entries": je_count}


# ─────────────────────────────────────────────────────────────────────────────
# Cleanup — marker-scoped PLUS TWO JOINS.
# ─────────────────────────────────────────────────────────────────────────────

def cleanup_reconciliation(
    db: Session, company: Company, *, execute: bool, quiet: bool = False
) -> dict:
    """Remove the reconciliation chain and postings THIS SEED created.

    ⚠️ THIS DELETES POSTED JOURNAL ENTRIES ON A LIVE TENANT. Not agent rows,
    not scaffolding — balanced two-legged entries that moved a real ledger. It
    is defensible only because this seed created them, today, as demo data; it
    is a different act from clearing a backlog and the dry run says so in those
    words rather than folding them into a row count.

    ⚠️ THE PAYMENTS GO TOO, AND THAT IS NOT OPTIONAL. Phase 3 is idempotent on
    `reference_number`, so a re-run SKIPS every existing payment — and the whole
    point of a re-seed is that those payments get new dates. Leave them and the
    re-seed silently reproduces the original failure with idempotence working
    perfectly the entire time. A cleanup that removed everything except the
    payments would read as complete and change nothing.

    ⚠️ THE DELETION ORDER IS FORCED, AND THE FK IS THE GUARD.
    `reconciliation_transactions.journal_entry_id` has NO `ON DELETE` — r154
    made that choice deliberately, so that a hard delete of an entry a cleared
    row points at is REFUSED rather than silently unlinking it. Transactions
    therefore go before the entries they reference. If this order is ever
    reversed the database refuses; it does not corrupt. Do not "fix" that by
    adding a cascade.
    """
    from sqlalchemy import text

    p = {"t": company.id}
    counts: dict[str, int] = {}

    # The demo's own feed rows, and the runs reachable from them.
    demo_txn_ids = [r[0] for r in db.execute(text(
        "SELECT id FROM bank_transactions WHERE tenant_id = :t "
        "AND plaid_transaction_id LIKE 'DEMO2-%'"
    ), p)]
    run_ids: list[str] = []
    if demo_txn_ids:
        run_ids = [r[0] for r in db.execute(text(
            "SELECT DISTINCT reconciliation_run_id FROM reconciliation_transactions "
            "WHERE bank_transaction_id = ANY(:ids)"
        ), {"ids": demo_txn_ids})]

    # ⚠️ SAFETY GATE — a run is only ours if EVERY line in it is ours. Plaid's
    # July rows live in their own run (verified: 16 transactions, zero DEMO2),
    # and that separation is what makes this deletion safe. If a run ever mixes
    # the two, deleting it would take Plaid's ingest demonstration with it —
    # so refuse and make a human look rather than delete the majority case.
    for rid in run_ids:
        total = db.execute(text(
            "SELECT count(*) FROM reconciliation_transactions "
            "WHERE reconciliation_run_id = :r"
        ), {"r": rid}).scalar()
        ours = db.execute(text(
            "SELECT count(*) FROM reconciliation_transactions "
            "WHERE reconciliation_run_id = :r AND bank_transaction_id = ANY(:ids)"
        ), {"r": rid, "ids": demo_txn_ids}).scalar()
        if total != ours:
            die(
                f"reconciliation run {rid} holds {total} transactions of which "
                f"only {ours} are this seed's. Deleting it would remove rows the "
                f"seed did not create. Refusing — a human should look."
            )

    je_from_txns = [r[0] for r in db.execute(text(
        "SELECT DISTINCT journal_entry_id FROM reconciliation_transactions "
        "WHERE reconciliation_run_id = ANY(:r) AND journal_entry_id IS NOT NULL"
    ), {"r": run_ids})] if run_ids else []
    je_from_payments = [r[0] for r in db.execute(text(
        "SELECT id FROM journal_entries WHERE tenant_id = :t "
        "AND reference_number LIKE 'DEMO2-PAY-%'"
    ), p)]
    je_ids = sorted(set(je_from_txns) | set(je_from_payments))

    pay_ids = [r[0] for r in db.execute(text(
        "SELECT id FROM customer_payments WHERE company_id = :t "
        "AND reference_number LIKE 'DEMO2-%'"
    ), p)]

    # ⚠️ THE INVOICES GO TOO, AND NOT BECAUSE THEY ARE WRONG. `post_payment`
    # mutated `amount_paid` and `status` on the invoices these payments settled;
    # deleting the payments does NOT undo that, so six invoices would be left
    # marked paid with nothing paying them. The re-seed's phase 3 validates each
    # application against the invoice BALANCE, and a fully-paid invoice has none
    # — so it would 400 rather than reproduce the demo. Recreating them via
    # phase 2 is cheaper and more honest than hand-resetting derived fields the
    # service owns. They carry no journal entries of their own (revenue does not
    # post — the known gap), so nothing is orphaned by their removal.
    inv_ids = [r[0] for r in db.execute(text(
        "SELECT id FROM invoices WHERE company_id = :t "
        "AND notes LIKE 'DEMO2 invoice for%'"
    ), p)]

    def n(sql: str, params: dict) -> int:
        return db.execute(text(sql), params).scalar() or 0

    counts["reconciliation_exceptions"] = n(
        "SELECT count(*) FROM reconciliation_exceptions "
        "WHERE reconciliation_run_id = ANY(:r)", {"r": run_ids}) if run_ids else 0
    counts["reconciliation_transactions"] = n(
        "SELECT count(*) FROM reconciliation_transactions "
        "WHERE reconciliation_run_id = ANY(:r)", {"r": run_ids}) if run_ids else 0
    counts["reconciliation_runs"] = len(run_ids)
    counts["journal_entries (POSTED)"] = len(je_ids)
    counts["customer_payment_applications"] = n(
        "SELECT count(*) FROM customer_payment_applications "
        "WHERE payment_id = ANY(:p)", {"p": pay_ids}) if pay_ids else 0
    counts["customer_payments"] = len(pay_ids)
    counts["invoice_lines"] = n(
        "SELECT count(*) FROM invoice_lines WHERE invoice_id = ANY(:i)",
        {"i": inv_ids}) if inv_ids else 0
    counts["invoices"] = len(inv_ids)
    counts["bank_transactions"] = len(demo_txn_ids)

    # `quiet` on the execute pass: the counts were already shown and
    # confirmed a moment ago, and reprinting the whole block under a
    # different mode header is how a reader loses track of which one
    # describes what actually happened.
    if not quiet:
        print("\n" + "=" * 68)
        print(f"DEMO-2 RECONCILIATION CLEANUP — {company.name} ({company.slug})")
        print(f"mode: {'EXECUTE' if execute else 'DRY-RUN (default)'}")
        print("=" * 68)
        for k, v in counts.items():
            print(f"    {k:<34} {v}")
        if je_ids:
            print(f"\n  ⚠️  {len(je_ids)} of those are POSTED JOURNAL ENTRIES — balanced")
            print("     two-legged entries that moved this tenant's real ledger. They")
            print("     are being deleted because THIS SEED created them today as demo")
            print("     data. That is a different act from clearing agent rows.")
        if run_ids:
            print(f"\n  runs to delete: {[r[:8] for r in run_ids]}")
            print("  Plaid's own run is NOT among them — every line in each run above")
            print("  traces to a DEMO2- bank transaction (verified, not assumed).")
    if not execute:
        print("\nDRY-RUN complete. Nothing was deleted.")
        return counts

    # ── ORDER IS THE CONTRACT — see the docstring. ────────────────────────
    if run_ids:
        db.execute(text("DELETE FROM reconciliation_exceptions "
                        "WHERE reconciliation_run_id = ANY(:r)"), {"r": run_ids})
        db.execute(text("DELETE FROM reconciliation_transactions "
                        "WHERE reconciliation_run_id = ANY(:r)"), {"r": run_ids})
        db.execute(text("DELETE FROM reconciliation_runs WHERE id = ANY(:r)"),
                   {"r": run_ids})
    # ⚠️ EVERYTHING HOLDING A POINTER INTO `journal_entries` GOES FIRST, AND THE
    # SET IS DERIVED FROM `pg_constraint`, NOT REASONED ABOUT. Inferring it from
    # which table "depends on" which put payments AFTER entries and the FK
    # refused — one step past where a guessed column name had already refused.
    # The authoritative set at r158:
    #
    #     customer_payments.journal_entry_id            ON DELETE NO ACTION
    #     reconciliation_transactions.journal_entry_id  ON DELETE NO ACTION
    #     journal_entry_lines.journal_entry_id          ON DELETE CASCADE
    #
    # Two must be cleared first; the third clears itself. And a FOURTH reference
    # exists that is NOT in that list — `customer_payments.discount_journal_
    # entry_id` holds an entry id with NO constraint, so it would dangle
    # silently rather than refuse. Harmless here (those payments are deleted
    # too), but it is why "the FK graph" and "every reference" are different
    # questions, and why the graph alone is not a safety proof.
    if pay_ids:
        db.execute(text("DELETE FROM customer_payment_applications "
                        "WHERE payment_id = ANY(:p)"), {"p": pay_ids})
        db.execute(text("DELETE FROM customer_payments WHERE id = ANY(:p)"),
                   {"p": pay_ids})
    # ⚠️ INVOICES NOW COME BEFORE JOURNAL ENTRIES, AND r170 IS WHY. INV-1 A-2
    # added `invoices.journal_entry_id` as an FK, so an invoice can point at an
    # entry — and deleting the entry first makes the FK refuse. The two blocks
    # below were the other way round until that column existed, and the ordering
    # was correct right up to the moment it was not.
    #
    # Caught by `test_seed_accounting_demo.py::test_children_are_deleted_before_
    # their_parents`, which DERIVES the constraint graph rather than restating a
    # hand-written order — so a new FK anywhere invalidates the sequence loudly
    # instead of waiting for a cleanup run to fail on real data.
    if inv_ids:
        # Lines before invoices — the FK points that way.
        db.execute(text("DELETE FROM invoice_lines WHERE invoice_id = ANY(:i)"),
                   {"i": inv_ids})
        db.execute(text("DELETE FROM invoices WHERE id = ANY(:i)"), {"i": inv_ids})
    if je_ids:
        # `journal_entry_id`, READ FROM THE MODEL, not `entry_id` — which is what
        # the relationship is NAMED (`back_populates="entry"`) and is not the
        # column. That guess reached a production write path and crashed the
        # execute; the single commit at the end is the only reason nothing
        # persisted. These lines DO cascade, so this delete is belt-and-braces —
        # kept so the script states what it removes.
        db.execute(text("DELETE FROM journal_entry_lines WHERE journal_entry_id = ANY(:j)"),
                   {"j": je_ids})
        db.execute(text("DELETE FROM journal_entries WHERE id = ANY(:j)"), {"j": je_ids})
    if demo_txn_ids:
        db.execute(text("DELETE FROM bank_transactions WHERE id = ANY(:b)"),
                   {"b": demo_txn_ids})
    db.flush()
    print("\n" + "=" * 68)
    print("DELETED — reconciliation chain, postings, payments and invoices:")
    for k, v in counts.items():
        if v:
            print(f"    {k:<34} {v}")
    print(f"    {'TOTAL':<34} {sum(counts.values())}")
    print("=" * 68)
    return counts


def cleanup(db: Session, company: Company) -> dict:
    """Marker scope alone is not enough, and both gaps are load-bearing.

    (1) `agent_anomalies` carry NO marker — they are reachable only through
        `agent_job_id → agent_jobs.tenant_id`. That is precisely the gap that
        left 206 unresolved anomalies pointing at deleted payments.
    (2) Reversal journal entries are CREATED by `_undo_entry` rather than
        deleted, so they carry no seed marker either and are reachable only by
        `reversal_of_entry_id`.
    """
    from sqlalchemy import text
    removed: dict[str, int] = {}

    removed["agent_anomalies"] = db.execute(text(
        "DELETE FROM agent_anomalies WHERE agent_job_id IN "
        "(SELECT id FROM agent_jobs WHERE tenant_id = :t AND report_pdf_path = :m)"
    ), {"t": company.id, "m": MARKER}).rowcount
    removed["agent_jobs"] = db.execute(text(
        "DELETE FROM agent_jobs WHERE tenant_id = :t AND report_pdf_path = :m"
    ), {"t": company.id, "m": MARKER}).rowcount
    removed["reversal_entries"] = db.execute(text(
        # TWO identifiers were wrong here and neither had ever run: the column is
        # `journal_entry_id` (not `entry_id`, which is the RELATIONSHIP name) and
        # journal_entries is on `tenant_id` (not `company_id` — this schema
        # carries both conventions). Latent because no reversal entries existed
        # yet; it would have crashed the first time one did.
        "DELETE FROM journal_entry_lines WHERE journal_entry_id IN "
        "(SELECT id FROM journal_entries WHERE tenant_id = :t "
        " AND reversal_of_entry_id IS NOT NULL)"
    ), {"t": company.id}).rowcount

    db.flush()
    say(f"agent-row cleanup — {removed}")
    # ⚠️ THIS NOTE USED TO SAY THE OPPOSITE AND IT WAS A LIE ON A DELETE PATH.
    # It read "invoices/payments/journal entries are NOT removed here", which
    # was true when only this function existed and false the moment
    # `cleanup_reconciliation` was added — so a run that had just deleted 15
    # posted journal entries printed a summary claiming it had not. A stale
    # reassurance after a destructive action is worse than no summary: it
    # invites the reader to stop checking. The two functions now report their
    # own work and neither speaks for the other.
    return removed


# ─────────────────────────────────────────────────────────────────────────────

_PHASES = {
    "0": ("preflight", None), "1": ("counterparties", phase_1_counterparties),
    "2": ("receivables", phase_2_receivables), "3": ("cash", phase_3_cash),
    "4": ("bank feed", None), "5": ("agents", phase_5_agents),
    "6": ("verify", None),
}


def main() -> None:
    ap = argparse.ArgumentParser(description="DEMO-2 accounting demo seed (phased).")
    ap.add_argument("--tenant-slug", required=True)
    ap.add_argument("--phase", default="all",
                    help="comma list (0,1,2) or 'all'. Phase 0 always runs first.")
    ap.add_argument("--cleanup", action="store_true",
                    help="Remove rows this seed created (DRY-RUN unless --execute).")
    ap.add_argument("--execute", action="store_true",
                    help="With --cleanup: actually delete. Requires a typed "
                         "confirmation when posted journal entries are involved.")
    args = ap.parse_args()

    db: Session = SessionLocal()
    try:
        company = db.query(Company).filter(Company.slug == args.tenant_slug).one_or_none()
        if company is None:
            die(f"no tenant with slug {args.tenant_slug!r}")
        actor = db.query(User).filter(
            User.company_id == company.id, User.is_active.is_(True)
        ).order_by(User.created_at).first()
        if actor is None:
            die(f"no active user on {args.tenant_slug!r} to attribute writes to")

        if args.cleanup:
            # ALWAYS dry-run first, whatever was asked: the counts are what the
            # confirmation below is confirming, so they must be computed and
            # shown BEFORE anything is deleted.
            counts = cleanup_reconciliation(db, company, execute=False)
            if not args.execute:
                print("Re-run with --cleanup --execute to delete.\n")
                return
            # ⚠️ A TYPED CONFIRMATION, AND IT IS NOT A FORMALITY. This deletes
            # posted journal entries from a live tenant. The guard's entire
            # value is that a HUMAN answers it — satisfying it from a pipe
            # would convert it into ceremony on the one operation where it is
            # most warranted, which is the same act as removing an alarm for
            # being inconvenient. `wipe_tenant` requires the same thing for the
            # same reason.
            if counts.get("journal_entries (POSTED)"):
                try:
                    typed = input(
                        f"\nType the tenant slug ({company.slug}) to confirm "
                        f"deleting {counts['journal_entries (POSTED)']} POSTED "
                        f"journal entries: "
                    ).strip()
                except EOFError:
                    die("no terminal to confirm on — this must be run by a human.")
                if typed != company.slug:
                    die("confirmation did not match — nothing deleted.")
            cleanup_reconciliation(db, company, execute=True, quiet=True)
            cleanup(db, company)
            db.commit()
            return

        wanted = (list("0123456") if args.phase == "all"
                  else [p.strip() for p in args.phase.split(",")])
        bad = [p for p in wanted if p not in _PHASES]
        if bad:
            die(f"unknown phase(s) {bad} — valid: {sorted(_PHASES)}")

        # Phase 0 ALWAYS runs, whatever was asked for: it is the gate, and a
        # phase that posts into an unconfigured ledger is the failure it exists
        # to prevent.
        account = phase_0_preflight(db, company, actor)

        for p in wanted:
            if p in ("0",):
                continue
            if p == "4":
                phase_4_bank_feed(db, company, actor, account)
            elif p == "6":
                phase_6_verify(db, company)
            else:
                _PHASES[p][1](db, company, actor)

        db.commit()
        say("committed.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
