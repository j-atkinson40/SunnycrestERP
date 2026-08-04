"""W-2 — Reconciliation test seed (case coverage, not volume).

Gives the reconciliation matcher real substrate so its behavior can be MEASURED
against a hand-computed expected table, and gives Books Review Phase 2 a queue with
genuine ambiguity. Targets a CLEAN tenant (default: sunnycrest, wiped in W-1) — the
matcher's candidate pool is ALL tenant CustomerPayment/VendorPayment in the window,
so ambient payments would pollute the result; a clean tenant is required.

W-2a FINDING (grounds case 10): run_matching iterates the run's BANK transactions and
looks UP payment candidates by amount. It never walks the other direction — a payment
with no bank line is never examined. So an outstanding check / in-transit payment is
structurally INVISIBLE: not "unmatched" (that's a transaction status), just unexamined.
The Class-D "outstanding item" exception card has NO producer in the current matcher —
surfacing it is a net-new query, a Phase-2 scope finding. Case 10 pins "no exception."

THE POOL IS PAYMENTS, NOT INVOICES (verified at HEAD, reconciliation_service.py):
customer_by_amount ← CustomerPayment (credit), vendor_by_amount ← VendorPayment (debit).
Invoices never enter matching; they exist here only for chain realism + the EPD case.

MONEY MATH: every amount is a hand-written literal with the arithmetic in a comment.
Nothing is generated from the matcher — the expected table (EXPECTED / EXPECTED_SUMMARY)
is derived from the CODE + hand-math and is a committed artifact BEFORE any run, so a
matcher bug and a seed bug are distinguishable.

Idempotent: re-run deletes W2-marked rows (marker prefix "W2-" / csv_file_path="W2SEED")
in FK order, then re-inserts. The W2- marker also lets the wipe tool clear it cleanly.

Usage:
  python -m scripts.seed_reconciliation_test [--tenant-slug sunnycrest]      # seed
  python -m scripts.seed_reconciliation_test --tenant-slug X --run-matcher   # W-2d: run + compare
Run --run-matcher TWICE for the non-idempotence demonstration (the 2nd run's
"changed since last state" section is the between-run diff).
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import date, datetime, timezone
from decimal import Decimal

from app.database import SessionLocal
from app.models.company import Company
from app.models.customer import Customer
from app.models.customer_payment import CustomerPayment
from app.models.financial_account import (
    FinancialAccount, ReconciliationRun, ReconciliationTransaction,
)
from app.models.invoice import Invoice
from app.services import reconciliation_service

MARKER = "W2SEED"                 # ReconciliationRun.csv_file_path
PFX = "W2-"                       # account_number / invoice number / payment reference prefix
UTC = timezone.utc

# ── Window (all payments + bank lines live inside it) ────────────────────────
PERIOD_START = date(2026, 7, 1)
STATEMENT_DATE = date(2026, 7, 31)
BASE = date(2026, 7, 15)         # most transactions dated here
OPENING_BALANCE = Decimal("10000.00")

def _pay_dt(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, 12, 0, tzinfo=UTC)

# ── Bulk clean matches — SCALE. 200 unique amounts $1000.00..$1199.00 step $1.00.
#    Each: 1 credit bank line + 1 customer payment, same amount, same day → the
#    single-candidate same-day path → auto_cleared 0.98.
#    Σ = Σ_{k=0}^{199}(1000 + k) = 200*1000 + (199*200)/2 = 200000 + 19900 = 219900.00
BULK_N = 200
BULK_SUM = Decimal("219900.00")  # hand-math above

# ── EPD arithmetic (case 6), shown: 4946.43 * 0.02 = 98.8286 → 98.93;
#    4946.43 - 98.93 = 4847.50. The deposit is 4847.50; NO payment of 4847.50 exists.
EPD_INVOICE = Decimal("4946.43")
EPD_DEPOSIT = Decimal("4847.50")   # 4946.43 - 98.93
EPD_DISCOUNT = Decimal("98.93")    # round(4946.43 * 0.02, 2)

# ── The expected table — derived from reconciliation_service.run_matching at HEAD.
#    Keyed by the per-transaction tag embedded in the description "[W2:<tag>] ...".
#    (status, confidence_or_None). Bulk handled by the "bulk-" prefix rule below.
EXPECTED = {
    # 1 — clean exact, same day → days_diff 0 → 0.98
    "1":        ("auto_cleared", Decimal("0.98")),
    # 2 — drift 5d (in window): txn 07-15, pay 07-10 → days_diff 5 → tier ">2,<=5" → 0.90
    "2":        ("auto_cleared", Decimal("0.90")),
    # 3 — drift 6d (boundary OUT): days_diff 6 > 5 → not cleared → unmatched
    "3":        ("unmatched", None),
    # 4 — forward ambiguity: 1 bank line, 2 payments same amount → len(candidates)=2 → unmatched
    "4a":       ("unmatched", None),
    "4b":       ("unmatched", None),
    # 5 — reverse ambiguity (destructive consumption): 2 bank lines, 1 payment.
    #     ORDER BY sort_order (verified line 52) → lower sort_order consumes the sole
    #     candidate; higher finds an empty pool. Determinate BECAUSE sort_order is set.
    "5-lo":     ("auto_cleared", Decimal("0.98")),   # same day
    "5-hi":     ("unmatched", None),                 # pool emptied by 5-lo
    # 6 — EPD ambiguity: 4847.50 deposit, no 4847.50 payment → unmatched (human decides
    #     discount-vs-shortpay; the matcher only sees no matching payment)
    "6":        ("unmatched", None),
    # 7 — one-to-many: 4847.50 deposit vs payments 1890.00/2142.50/815.00 (Σ=4847.50,
    #     none equals 4847.50) → no single-amount candidate → unmatched. The 3 payments
    #     are never examined (no bank line of their amounts).
    "7":        ("unmatched", None),
    # 8 — unidentified inflow: credit with no payment → unmatched
    "8":        ("unmatched", None),
    # 9 — keyword ladder short-circuits (confidences are the code's literals):
    "9-fee":    ("bank_fee", Decimal("0.90")),       # "SERVICE CHARGE" → 0.90, suggested
    "9-payroll":("payroll", Decimal("0.92")),        # "PAYROLL"/"ADP"  → 0.92, AUTO, subtracts
    "9-nsf":    ("nsf", Decimal("0.88")),            # "NSF"/"RETURNED" → 0.88, suggested
    # 10 — ledger orphan: a payment with no bank line. No transaction, no status. Pinned
    #      as "produces no exception" per W-2a. (Asserted by the payment's continued
    #      existence + absence from any transaction, checked in the report.)
}

# ── Case amounts (all OUTSIDE the bulk $1000..$1199 band + distinct from each other,
#    so no cross-case pool pollution). Debits are NEGATIVE (sign drives cleared_total).
A1 = Decimal("525.00")   # case 1
A2 = Decimal("612.50")   # case 2
A3 = Decimal("733.00")   # case 3
A4a = Decimal("488.00")  # case 4a (2 payments)
A4b = Decimal("496.00")  # case 4b (2 payments)
A5 = Decimal("850.00")   # case 5 (2 bank lines, 1 payment)
A8 = Decimal("377.00")   # case 8 (no payment)
A9_FEE = Decimal("-45.00")      # debit
A9_PAYROLL = Decimal("-3200.00")# debit, auto-clears, SUBTRACTS from cleared_total
A9_NSF = Decimal("-500.00")     # debit
A10 = Decimal("999.99")  # case 10 orphan payment (unique; nothing matches it)
C7 = [Decimal("1890.00"), Decimal("2142.50"), Decimal("815.00")]  # Σ = 4847.50

# ── Expected RUN SUMMARY (hand-computed) ─────────────────────────────────────
# cleared_total = Σ signed amount over auto_cleared + payroll:
#   bulk 219900.00 + case1 525.00 + case2 612.50 + case5-lo 850.00 + payroll (-3200.00)
#   = 219900.00 + 525.00 + 612.50 + 850.00 - 3200.00 = 218687.50
EXPECTED_CLEARED = Decimal("218687.50")
# closing chosen so difference is the SENTINEL 0.00 (a payroll sign-flip would make
# cleared 225087.50 and difference 228687.50-10000-225087.50 = -6400.00):
STATEMENT_CLOSING = Decimal("228687.50")  # = OPENING 10000.00 + EXPECTED_CLEARED 218687.50
EXPECTED_DIFFERENCE = Decimal("0.00")     # 228687.50 - 10000.00 - 218687.50
# Counts: auto = 200 bulk + case1 + case2 + case5-lo + payroll = 204
#         suggested = bank_fee + nsf = 2 ; unmatched = 3,4a,4b,5-hi,6,7,8 = 7 ; total = 213
EXPECTED_SUMMARY = {
    "auto_cleared": 204, "suggested": 2, "unmatched": 7, "total_transactions": 213,
    "platform_cleared_balance": EXPECTED_CLEARED, "difference": EXPECTED_DIFFERENCE,
}


def _die(msg):
    print(f"\n❌ {msg}", file=sys.stderr)
    sys.exit(1)


def cleanup_existing(db, tid):
    """Delete W2-marked rows in FK-safe order (idempotence). Runs (cascade txns)
    first, then payments, invoices, customers, financial account."""
    from sqlalchemy import text
    from sqlalchemy import or_
    from app.models.customer_payment import CustomerPaymentApplication
    # runs (cascade deletes reconciliation_transactions via ondelete=CASCADE)
    db.query(ReconciliationRun).filter(
        ReconciliationRun.tenant_id == tid, ReconciliationRun.csv_file_path == MARKER,
    ).delete(synchronize_session=False)
    # customer_payment_applications reference payments AND invoices with no cascade.
    # The Arc B Accept flow creates them (payment→invoice); the seed never does.
    # Delete them before the payments/invoices they point at, or the FK bites.
    w2_pay = [r[0] for r in db.query(CustomerPayment.id).filter(
        CustomerPayment.company_id == tid,
        CustomerPayment.reference_number.like(f"{PFX}%")).all()]
    w2_inv = [r[0] for r in db.query(Invoice.id).filter(
        Invoice.company_id == tid, Invoice.number.like(f"{PFX}%")).all()]
    if w2_pay or w2_inv:
        conds = []
        if w2_pay:
            conds.append(CustomerPaymentApplication.payment_id.in_(w2_pay))
        if w2_inv:
            conds.append(CustomerPaymentApplication.invoice_id.in_(w2_inv))
        db.query(CustomerPaymentApplication).filter(or_(*conds)).delete(
            synchronize_session=False)
    db.query(CustomerPayment).filter(
        CustomerPayment.company_id == tid,
        CustomerPayment.reference_number.like(f"{PFX}%"),
    ).delete(synchronize_session=False)
    db.query(Invoice).filter(
        Invoice.company_id == tid, Invoice.number.like(f"{PFX}%"),
    ).delete(synchronize_session=False)
    db.query(Customer).filter(
        Customer.company_id == tid, Customer.account_number.like(f"{PFX}%"),
    ).delete(synchronize_session=False)
    db.query(FinancialAccount).filter(
        FinancialAccount.tenant_id == tid, FinancialAccount.account_name == "W2 Test Operating",
    ).delete(synchronize_session=False)
    db.commit()


def seed(db, tid):
    """Create the full chain: financial account → customers → invoices → payments →
    bank transactions (one ReconciliationRun holding all bank lines)."""
    import uuid

    def _cust(i, name):
        c = Customer(id=str(uuid.uuid4()), company_id=tid, name=name,
                     account_number=f"{PFX}{i}", is_active=True)
        db.add(c)
        return c

    def _inv(cust, i, total):
        iv = Invoice(id=str(uuid.uuid4()), company_id=tid, customer_id=cust.id,
                     number=f"{PFX}INV-{i}", status="sent",
                     invoice_date=_pay_dt(BASE), due_date=_pay_dt(STATEMENT_DATE),
                     subtotal=total, total=total)
        db.add(iv)
        return iv

    def _pay(cust, amount, when: date, ref):
        p = CustomerPayment(id=str(uuid.uuid4()), company_id=tid, customer_id=cust.id,
                            payment_date=_pay_dt(when), total_amount=amount,
                            payment_method="check", reference_number=ref)
        db.add(p)
        return p

    txns = []  # (tag, txn_date, description, amount, transaction_type)

    def _bank(tag, amount, when: date, ttype, desc):
        txns.append((tag, when, f"[W2:{tag}] {desc}", amount, ttype))

    # bank account to reconcile (sunnycrest has 0 — required NOT NULL FK on the run)
    acct = FinancialAccount(id=str(uuid.uuid4()), tenant_id=tid,
                            account_type="checking", account_name="W2 Test Operating")
    db.add(acct)
    db.flush()

    # ---- bulk: 200 clean same-day matches, unique amounts 1000.00..1199.00 ----
    bulk_cust = _cust(9000, "W2 Bulk Deposits")
    for k in range(BULK_N):
        amt = Decimal("1000.00") + Decimal(k)  # 1000.00, 1001.00, ... 1199.00
        _pay(bulk_cust, amt, BASE, f"{PFX}PAY-bulk-{k}")
        _bank(f"bulk-{k}", amt, BASE, "credit", f"deposit {amt}")

    # ---- case 1: clean exact, same day ----
    c1 = _cust(1, "Case1 Hopkins FH")
    _inv(c1, 1, A1)
    _pay(c1, A1, BASE, f"{PFX}PAY-1")
    _bank("1", A1, BASE, "credit", f"deposit {A1}")

    # ---- case 2: drift 5 days (pay 07-10, txn 07-15) ----
    c2 = _cust(2, "Case2 Riverside FH")
    _inv(c2, 2, A2)
    _pay(c2, A2, date(2026, 7, 10), f"{PFX}PAY-2")
    _bank("2", A2, BASE, "credit", f"deposit {A2}")

    # ---- case 3: drift 6 days (pay 07-09, txn 07-15) → OUT of window ----
    c3 = _cust(3, "Case3 Lakeside FH")
    _inv(c3, 3, A3)
    _pay(c3, A3, date(2026, 7, 9), f"{PFX}PAY-3")
    _bank("3", A3, BASE, "credit", f"deposit {A3}")

    # ---- case 4: forward ambiguity — 1 bank line, 2 payments same amount (×2 instances) ----
    c4 = _cust(4, "Case4 Twin Pines FH")
    _inv(c4, 4, A4a)
    _pay(c4, A4a, BASE, f"{PFX}PAY-4a-i"); _pay(c4, A4a, BASE, f"{PFX}PAY-4a-ii")
    _bank("4a", A4a, BASE, "credit", f"deposit {A4a} (2 candidate payments)")
    _pay(c4, A4b, BASE, f"{PFX}PAY-4b-i"); _pay(c4, A4b, BASE, f"{PFX}PAY-4b-ii")
    _bank("4b", A4b, BASE, "credit", f"deposit {A4b} (2 candidate payments)")

    # ---- case 5: reverse ambiguity — 2 bank lines, 1 payment. sort_order set below so
    #      5-lo (lower sort_order) consumes the sole candidate, 5-hi finds empty pool. ----
    c5 = _cust(5, "Case5 Meadowbrook FH")
    _inv(c5, 5, A5)
    _pay(c5, A5, BASE, f"{PFX}PAY-5")
    _bank("5-lo", A5, BASE, "credit", f"deposit {A5} (first of two identical)")
    _bank("5-hi", A5, BASE, "credit", f"deposit {A5} (second — pool already consumed)")

    # ---- case 6: EPD ambiguity — invoice 4946.43, deposit 4847.50, NO 4847.50 payment ----
    c6 = _cust(6, "Case6 Cedar Grove FH")
    _inv(c6, 6, EPD_INVOICE)  # full invoice 4946.43; discount 98.93 = 2%
    _bank("6", EPD_DEPOSIT, BASE, "credit", f"deposit {EPD_DEPOSIT} vs invoice {EPD_INVOICE} (discount or short-pay?)")

    # ---- case 7: one-to-many — deposit 4847.50 vs 3 payments summing to it ----
    c7 = _cust(7, "Case7 Willowdale FH")
    _inv(c7, 7, sum(C7))  # 4847.50
    for j, amt in enumerate(C7):
        _pay(c7, amt, BASE, f"{PFX}PAY-7-{j}")
    _bank("7", Decimal("4847.50"), BASE, "credit", "deposit 4847.50 vs three payments 1890.00/2142.50/815.00")

    # ---- case 8: unidentified inflow — credit, no payment ----
    c8 = _cust(8, "Case8 Unknown Payer")
    _bank("8", A8, BASE, "credit", f"unidentified deposit {A8}")

    # ---- case 9: keyword ladder — fee (sug), payroll (AUTO, subtracts), nsf (sug) ----
    _bank("9-fee", A9_FEE, BASE, "debit", "MONTHLY SERVICE CHARGE")
    _bank("9-payroll", A9_PAYROLL, BASE, "debit", "ADP PAYROLL RUN")
    _bank("9-nsf", A9_NSF, BASE, "debit", "NSF RETURNED ITEM")

    # ---- case 10: ledger orphan — payment with NO bank line (unique amount) ----
    c10 = _cust(10, "Case10 Outstanding Check Payer")
    _inv(c10, 10, A10)
    _pay(c10, A10, BASE, f"{PFX}PAY-10")   # no _bank(...) → invisible to the matcher

    db.flush()

    # ---- the reconciliation run + its bank transactions ----
    run = ReconciliationRun(
        id=str(uuid.uuid4()), tenant_id=tid, financial_account_id=acct.id,
        status="in_review", statement_date=STATEMENT_DATE,
        statement_closing_balance=STATEMENT_CLOSING, opening_balance=OPENING_BALANCE,
        period_start=PERIOD_START, period_end=STATEMENT_DATE,
        total_statement_transactions=len(txns), csv_file_path=MARKER,
    )
    db.add(run)
    db.flush()

    # sort_order: deterministic + reproducible. Case 5 must be adjacent with lo<hi;
    # everything else just needs distinct, stable values → enumerate insertion order.
    for order, (tag, when, desc, amount, ttype) in enumerate(txns):
        db.add(ReconciliationTransaction(
            id=str(uuid.uuid4()), tenant_id=tid, reconciliation_run_id=run.id,
            transaction_date=when, description=desc, amount=amount,
            transaction_type=ttype, reference_number=None,  # NULL → reference path inert
            sort_order=order,
        ))
    db.commit()
    return run.id, len(txns)


# ── W-2d: run the matcher + compare to the committed expected table ───────────
_TAG_RE = re.compile(r"\[W2:([^\]]+)\]")


def _snapshot(db, run_id):
    rows = db.query(ReconciliationTransaction).filter(
        ReconciliationTransaction.reconciliation_run_id == run_id).all()
    return {r.id: (r.match_status, r.match_confidence, r.matched_record_id,
                   _TAG_RE.search(r.description).group(1) if _TAG_RE.search(r.description) else "?")
            for r in rows}


def run_matcher_and_report(db, tid):
    run = db.query(ReconciliationRun).filter(
        ReconciliationRun.tenant_id == tid, ReconciliationRun.csv_file_path == MARKER,
    ).first()
    if not run:
        _die("No W2SEED reconciliation run found — seed first.")

    pre = _snapshot(db, run.id)
    result = reconciliation_service.run_matching(db, run, tid)
    db.commit()
    post = _snapshot(db, run.id)

    print("=" * 72)
    print(f"MATCHER RUN vs EXPECTED — tenant={tid}  run={run.id}")
    print("=" * 72)

    # per-case comparison (bulk aggregated)
    mism = 0
    bulk_ok = bulk_bad = 0
    print("\nPER-CASE (actual vs expected):")
    for txn_id, (status, conf, mrec, tag) in sorted(post.items(), key=lambda x: x[1][3]):
        if tag.startswith("bulk"):
            exp = ("auto_cleared", Decimal("0.98"))
            ok = (status == exp[0] and conf == exp[1])
            bulk_ok += ok
            bulk_bad += (not ok)
            continue
        exp = EXPECTED.get(tag)
        if exp is None:
            print(f"    ? {tag:<10} actual={status}/{conf}  (no expected entry)")
            continue
        ok = (status == exp[0] and (exp[1] is None or conf == exp[1]))
        mark = "✓" if ok else "✗ MISMATCH"
        mism += (not ok)
        print(f"    {mark:<11} {tag:<10} expected {exp[0]}/{exp[1]}   actual {status}/{conf}")
    print(f"    ✓ bulk       {bulk_ok}/{BULK_N} auto_cleared@0.98" + (f"   ✗ {bulk_bad} OFF" if bulk_bad else ""))

    # case 10 — the orphan must exist and be untouched (no transaction, no status)
    orphan = db.query(CustomerPayment).filter(
        CustomerPayment.company_id == tid, CustomerPayment.reference_number == f"{PFX}PAY-10").first()
    orphan_tagged = any(t[3] == "10" for t in post.values())
    print(f"\nCASE 10 (ledger orphan): payment exists={orphan is not None}  "
          f"appears as a transaction={orphan_tagged}  → "
          f"{'produces NO exception (W-2a confirmed)' if orphan and not orphan_tagged else 'UNEXPECTED'}")

    # summary vs expected
    total = len(post)
    auto = sum(1 for v in post.values() if v[0] in ("auto_cleared", "payroll"))
    print("\nRUN SUMMARY (actual vs expected):")
    for k, exp in EXPECTED_SUMMARY.items():
        act = {"auto_cleared": result["auto_cleared"], "suggested": result["suggested"],
               "unmatched": result["unmatched"], "total_transactions": total,
               "platform_cleared_balance": run.platform_cleared_balance,
               "difference": run.difference}[k]
        mark = "✓" if str(act) == str(exp) else "✗ MISMATCH"
        mism += (str(act) != str(exp))
        print(f"    {mark:<11} {k:<26} expected {exp}   actual {act}")

    rate = (auto / total * 100) if total else 0
    print(f"\nAUTO-MATCH RATE: {auto}/{total} = {rate:.1f}%")

    # between-run diff (empty on run 1 baseline; the signal on run 2)
    changed = [(post[i][3], pre[i][0], post[i][0], pre[i][2], post[i][2])
               for i in post if pre.get(i) and (pre[i][0] != post[i][0] or pre[i][2] != post[i][2])]
    print(f"\nCHANGED SINCE LAST STATE: {len(changed)} transaction(s)")
    for tag, s0, s1, m0, m1 in sorted(changed)[:40]:
        print(f"    {tag:<12} status {s0}→{s1}   matched_id {m0}→{m1}")
    if len([c for c in changed if not c[0].startswith('bulk')]) == 0 and changed:
        print("    (all changes are bulk unmatched→auto_cleared — first classification)")

    print(f"\n{'✅ ALL MATCH EXPECTED' if mism == 0 else f'⚠️  {mism} MISMATCH(es) vs expected'}")
    return mism


def main():
    ap = argparse.ArgumentParser(description="W-2 reconciliation test seed.")
    ap.add_argument("--tenant-slug", default="sunnycrest")
    ap.add_argument("--run-matcher", action="store_true",
                    help="Run the matcher on the seeded run + compare to the committed expected "
                         "table (W-2d). Run twice for the non-idempotence demonstration.")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        co = db.query(Company).filter(Company.slug == args.tenant_slug).first()
        if not co:
            _die(f"No tenant with slug '{args.tenant_slug}'.")
        tid = co.id

        if args.run_matcher:
            sys.exit(1 if run_matcher_and_report(db, tid) else 0)

        cleanup_existing(db, tid)
        run_id, n = seed(db, tid)
        print(f"✅ Seeded W2 reconciliation test into '{args.tenant_slug}' (id={tid}).")
        print(f"   run_id={run_id}  bank_transactions={n}  "
              f"(expected auto {EXPECTED_SUMMARY['auto_cleared']} / "
              f"suggested {EXPECTED_SUMMARY['suggested']} / unmatched {EXPECTED_SUMMARY['unmatched']})")
        print("   Re-run with --run-matcher to measure the matcher against the expected table.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
