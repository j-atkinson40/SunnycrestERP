"""DEMO-1 — the seed-posting ratchet (financial-model writes in seed scripts).

THE DECIDED RULE (2026-08-08): **a seed posts through the services.**
`create_customer_payment` -> `post_payment`, `book_keyword_entry`,
`book_coded_entry`, the triage accept handlers. Not `CustomerPayment(...)`
+ `db.add`.

WHY IT NEEDS A GATE AND NOT JUST A CONVENTION. A seed that constructs a
`CustomerPayment` directly produces a payment row and NO journal entry —
`post_payment` is never reached, so nothing posts. The result is the exact
failure mode a demo cannot survive: data that exists and books that do not
move. It is invisible in review (the seed runs, rows appear, the page renders
a number) and it is only detectable by asking a question nobody asks of a
seed — "did the ledger move?" The DEMO-1 investigation found ZERO seeds in
this repo going through the service layer; the one hit for `sales_service.`
in `scripts/` is `seed_staging.py:1109`'s `create_quote`, which posts nothing.

TWO PREDICATES, BECAUSE THERE ARE TWO WAYS TO WRITE A ROW — and this is the
part a single-predicate gate gets wrong while reading as complete:

  * 32 ORM construction sites (16 file/model pairs, 3 files) build a guarded
    model directly. This is the obvious half.
  * 4 RAW-SQL `INSERT INTO` sites (4 pairs, 1 file). `seed_staging.py` writes
    invoices, invoice lines, payments and payment applications as raw SQL
    (`seed_staging.py:961,981`). A model-name predicate cannot see ANY of
    them. Guarding only construction would have declared this class closed
    while the largest seed in the repo wrote financial rows past the gate.

The route-write ratchet (`test_route_write_ratchet.py`) is the sibling of
this gate: same enumerable-predicate discipline, same allowlist-as-visible-
act, different surface (routes vs seeds). `FINANCIAL_MODELS` is imported
from it rather than restated — ONE DEFINITION, TWO READERS, so a model added
to the guarded set is guarded on both surfaces at once and the two cannot
drift into disagreeing about what "financial model" means.

To legitimately add a write site you must EITHER route it through a service
(the point) OR add it to the relevant allowlist with a comment saying why —
and that edit is the visible, reviewable act the ratchet exists to force.
Draining a site means REMOVING its entry, so the count can only shrink.

Pure static analysis for the two ratchets — no DB, no imports, fast. The
third test imports `app.models` (no DB) to hold the two predicates in step.
"""
from __future__ import annotations

import pathlib
import re
from collections import Counter

from tests.test_route_write_ratchet import FINANCIAL_MODELS

_SEEDS_DIR = pathlib.Path(__file__).resolve().parents[1] / "scripts"
_SEED_GLOB = "seed_*.py"

# The raw-SQL counterpart of FINANCIAL_MODELS. Hand-maintained, and
# `test_guarded_models_and_tables_stay_in_step` is what keeps it honest —
# a model added to FINANCIAL_MODELS with no table here fails that test.
FINANCIAL_TABLES = [
    "journal_entries", "journal_entry_lines",
    "reconciliation_runs", "reconciliation_transactions",
    "reconciliation_adjustments",
    "invoices", "invoice_lines",
    "customer_payments", "customer_payment_applications",
    "vendor_bills", "vendor_bill_lines", "vendor_payments",
    "purchase_orders", "purchase_order_lines",
    "statement_run_items",
]

# ⚠️ PINNED WRONGNESS, INHERITED NOT INTRODUCED. Two names in the route
# ratchet's FINANCIAL_MODELS do not exist as models — `FinanceCharge` (the
# real models are `FinanceChargeRun` / `FinanceChargeItem`) and `Statement`
# (`StatementRun` / `CustomerStatement`). They can never match, on either
# surface, so both ratchets' predicates are two names narrower than they
# read. Pinned rather than fixed: correcting the route ratchet's list is its
# own change with its own re-scan, and silently dropping them here would hide
# the gap. Remove a name from this set when the sibling list is corrected.
KNOWN_PHANTOM_MODELS = {"FinanceCharge", "Statement"}

# Current grandfathered ORM construction sites, {(seed file, model): count}.
# All three files predate the rule. None of them posts.
CONSTRUCTION_ALLOWLIST: dict[tuple[str, str], int] = {
    # Agent-fixture seed — builds AR substrate for the accounting agents.
    ("seed_agent_test.py", "CustomerPayment"): 4,
    ("seed_agent_test.py", "CustomerPaymentApplication"): 1,
    ("seed_agent_test.py", "Invoice"): 3,
    # Full-year agent E2E — also hand-builds its own journal entries, which
    # is precisely the second-definition-of-posting-arithmetic this rule
    # exists to stop (8 JournalEntryLine sites).
    ("seed_full_year_e2e.py", "CustomerPayment"): 1,
    ("seed_full_year_e2e.py", "CustomerPaymentApplication"): 1,
    ("seed_full_year_e2e.py", "Invoice"): 2,
    ("seed_full_year_e2e.py", "InvoiceLine"): 1,
    ("seed_full_year_e2e.py", "JournalEntry"): 4,
    ("seed_full_year_e2e.py", "JournalEntryLine"): 8,
    ("seed_full_year_e2e.py", "VendorBill"): 1,
    ("seed_full_year_e2e.py", "VendorBillLine"): 1,
    ("seed_full_year_e2e.py", "VendorPayment"): 1,
    # W-2 reconciliation seed. Deliberately NOT drained: its committed
    # EXPECTED table is a measurement fixture authored BEFORE any run so a
    # matcher bug and a seed bug stay distinguishable, and posting through
    # services would create journal entries that table does not predict.
    ("seed_reconciliation_test.py", "CustomerPayment"): 1,
    ("seed_reconciliation_test.py", "Invoice"): 1,
    ("seed_reconciliation_test.py", "ReconciliationRun"): 1,
    ("seed_reconciliation_test.py", "ReconciliationTransaction"): 1,
}

# Current grandfathered raw-SQL insert sites, {(seed file, table): count}.
CONSTRUCTION_ALLOWLIST_SQL: dict[tuple[str, str], int] = {
    # seed_staging's cleanup-then-insert AR block (seed_staging.py:961,981).
    # Invisible to the model-name predicate — the reason this gate has two.
    ("seed_staging.py", "invoices"): 1,
    ("seed_staging.py", "invoice_lines"): 1,
    ("seed_staging.py", "customer_payments"): 1,
    ("seed_staging.py", "customer_payment_applications"): 1,
}

_MODEL_PATTERN = re.compile(
    r"\b(" + "|".join(sorted(FINANCIAL_MODELS, key=len, reverse=True)) + r")\("
)
_SQL_PATTERN = re.compile(
    r"INSERT\s+INTO\s+(" + "|".join(sorted(FINANCIAL_TABLES, key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)


def _scan(pattern: re.Pattern, *, lower: bool = False) -> dict[tuple[str, str], int]:
    """{(seed filename, match): count} across `scripts/seed_*.py`.

    `Model(` distinguishes construction from `query(Model)` (which has
    `Model)`). Comment lines are skipped so a doc reference is not a
    violation — the same convention the route ratchet uses.
    """
    sites: Counter = Counter()
    for f in sorted(_SEEDS_DIR.glob(_SEED_GLOB)):
        for line in f.read_text().splitlines():
            if line.strip().startswith("#"):
                continue
            for match in pattern.findall(line):
                sites[(f.name, match.lower() if lower else match)] += 1
    return dict(sites)


def _assert_ratchet(live: dict, expected: dict, *, surface: str, remedy: str) -> None:
    added = {k: live[k] for k in live if live[k] > expected.get(k, 0)}
    removed = {k: expected[k] for k in expected if expected.get(k, 0) > live.get(k, 0)}

    msg = []
    if added:
        msg.append(f"NEW {surface} in a seed ({remedy}):")
        for (f, m), n in sorted(added.items()):
            msg.append(f"  + {f}::{m} (now x{n}, allowed x{expected.get((f, m), 0)})")
    if removed:
        msg.append(f"A {surface} site was DRAINED (good) — remove/lower its allowlist entry:")
        for (f, m), n in sorted(removed.items()):
            msg.append(f"  - {f}::{m} (allowed x{n}, now x{live.get((f, m), 0)})")

    assert live == expected, "\n".join(msg)


def test_no_new_financial_model_construction_in_seeds():
    """A seed may not build a guarded financial model directly."""
    _assert_ratchet(
        _scan(_MODEL_PATTERN),
        CONSTRUCTION_ALLOWLIST,
        surface="financial-model construction",
        remedy="post it through the service — create_customer_payment / "
               "post_invoice_to_ar / book_keyword_entry / book_coded_entry — "
               "or add it to CONSTRUCTION_ALLOWLIST with a reason",
    )


def test_no_new_raw_sql_financial_insert_in_seeds():
    """Nor may it reach past the ORM to insert the same row as raw SQL.

    Separate from the construction gate because it is a separate way to miss
    the service, and because the model-name predicate is structurally blind
    to it — not because the two are different offences.
    """
    _assert_ratchet(
        _scan(_SQL_PATTERN, lower=True),
        CONSTRUCTION_ALLOWLIST_SQL,
        surface="raw-SQL financial insert",
        remedy="post it through the service, or add it to "
               "CONSTRUCTION_ALLOWLIST_SQL with a reason",
    )


def test_guarded_models_and_tables_stay_in_step():
    """The two predicates guard the same set, or the gate has a silent hole.

    A model added to FINANCIAL_MODELS whose table is absent from
    FINANCIAL_TABLES is guarded against construction and NOT against raw SQL
    — which is exactly the shape of the seed_staging blind spot, one layer
    up. Imports `app.models` (no DB) so the mapping is authoritative rather
    than a third hand-maintained list.
    """
    import app.models as models

    missing_table: list[str] = []
    phantom: set[str] = set()

    for name in FINANCIAL_MODELS:
        model = getattr(models, name, None)
        if model is None:
            phantom.add(name)
            continue
        table = getattr(model, "__tablename__", None)
        if table not in FINANCIAL_TABLES:
            missing_table.append(f"{name} -> {table}")

    assert not missing_table, (
        "Guarded model(s) whose table is not in FINANCIAL_TABLES — the "
        "raw-SQL gate cannot see writes to them:\n  "
        + "\n  ".join(sorted(missing_table))
    )
    assert phantom == KNOWN_PHANTOM_MODELS, (
        "The set of non-existent names in FINANCIAL_MODELS changed.\n"
        f"  live:   {sorted(phantom)}\n"
        f"  pinned: {sorted(KNOWN_PHANTOM_MODELS)}\n"
        "If a name was corrected in test_route_write_ratchet.py, drop it "
        "from KNOWN_PHANTOM_MODELS here. If a NEW name was added that does "
        "not resolve, it is a typo — a guarded model that can never match."
    )
