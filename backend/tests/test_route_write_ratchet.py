"""S-5 — the route-write ratchet (financial-model construction in routes).

TWO NUMBERS, and they answer different questions — record BOTH so nobody
later reads the small one as "this class is nearly solved":

  * 479 handlers / 100 route files do SOME direct DB write (add/commit/
    delete). That is the REAL size of the logic-in-routes class — the
    roadmap-slot number. It says logic-in-routes is architectural debt, not
    cleanup. This gate does NOT try to hold that line (most of the 479 are
    legitimate simple CRUD; a blanket "no db.commit in a route" gate would
    grandfather 479 entries and teach that the allowlist is where things go).

  * 5 construction sites (4 file/model pairs) directly build a CORE
    FINANCIAL model in a route. That is the GATEABLE subset — the places
    where a financial guard (period lock, balance, tenant scope) needs a
    service chokepoint and can't get one because the write is inline. The
    arc's extractions (JE -> journal_entry_service, reconciliation matching
    + create_adjustment -> reconciliation_service) drained the rest down to
    these. (An earlier pass reported "2" — that used a narrower model set
    and undercounted; the honest full-predicate number is 5.)

THE PREDICATE IS ENUMERABLE, NOT A JUDGMENT CALL — an explicit list of
model names checked by name. "Financial model" as a category someone
assesses per-case erodes within two arcs; a name list does not. To add a
model to the guarded set, add its name to FINANCIAL_MODELS. To legitimately
add a new construction site, you must EITHER route it through a service
(preferred) OR add it to ALLOWLIST with a comment saying why — and that
edit is the visible, reviewable act the ratchet exists to force.

This test is pure static analysis of source files — no DB, fast,
deterministic — so it belongs in the scoped CI gate.
"""
from __future__ import annotations

import pathlib
import re
from collections import Counter

# The enumerable predicate: core financial-domain models. Checked BY NAME.
FINANCIAL_MODELS = [
    "JournalEntry", "JournalEntryLine",
    "ReconciliationRun", "ReconciliationTransaction", "ReconciliationAdjustment",
    "Invoice", "InvoiceLine",
    "CustomerPayment", "CustomerPaymentApplication",
    "VendorBill", "VendorBillLine", "VendorPayment",
    "PurchaseOrder", "PurchaseOrderLine",
    "FinanceCharge", "Statement", "StatementRunItem",
]

# Current grandfathered construction sites, {(file, model): count}. The
# ratchet fails if the live set differs — a NEW site (new pair or higher
# count) must be drained to a service or explicitly added here with a
# justification. Draining a site (moving it to a service) means REMOVING its
# entry here. As of S-5 (create_adjustment drained), these 5 remain:
ALLOWLIST: dict[tuple[str, str], int] = {
    ("purchasing.py", "PurchaseOrder"): 1,       # create_order — multi-line PO + number-gen (the 479 class)
    ("purchasing.py", "PurchaseOrderLine"): 1,   # create_order line items
    ("reconciliation.py", "ReconciliationRun"): 1,        # start_run — ingestion
    ("reconciliation.py", "ReconciliationTransaction"): 2,  # populate_from_feed + upload_csv — ingestion
}

_ROUTES_DIR = pathlib.Path(__file__).resolve().parents[1] / "app" / "api" / "routes"
_PATTERN = re.compile(
    r"\b(" + "|".join(sorted(FINANCIAL_MODELS, key=len, reverse=True)) + r")\("
)


def _scan_construction_sites() -> Counter:
    """{(relpath, model): count} for every construction (`Model(`) of a
    guarded model in a route file. `Model(` distinguishes construction from
    `query(Model)` (which has `Model)`); comment lines are skipped."""
    sites: Counter = Counter()
    for f in sorted(_ROUTES_DIR.rglob("*.py")):
        for line in f.read_text().splitlines():
            if line.strip().startswith("#"):
                continue
            for model in _PATTERN.findall(line):
                sites[(str(f.relative_to(_ROUTES_DIR)), model)] += 1
    return sites


def test_no_new_financial_model_construction_in_routes():
    live = _scan_construction_sites()
    live_set = dict(live)
    expected = dict(ALLOWLIST)

    added = {k: live_set[k] for k in live_set if live_set[k] > expected.get(k, 0)}
    removed = {k: expected[k] for k in expected if expected.get(k, 0) > live_set.get(k, 0)}

    msg_lines = []
    if added:
        msg_lines.append(
            "NEW financial-model construction in a route (route the write "
            "through a service, or add it to ALLOWLIST with a reason):"
        )
        for (f, m), n in sorted(added.items()):
            msg_lines.append(f"  + {f}::{m} (now x{n}, allowed x{expected.get((f, m), 0)})")
    if removed:
        msg_lines.append(
            "A site was DRAINED (good) — remove/lower its ALLOWLIST entry to "
            "ratchet down:"
        )
        for (f, m), n in sorted(removed.items()):
            msg_lines.append(f"  - {f}::{m} (allowed x{n}, now x{live_set.get((f, m), 0)})")

    assert live_set == expected, "\n".join(msg_lines)
