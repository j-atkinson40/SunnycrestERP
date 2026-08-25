"""LEDGER-1 A-1 — characterization of the Sage COA category classifier.

⚠️ THESE TESTS PIN BEHAVIOUR THAT IS WRONG, ON PURPOSE. Per CLAUDE.md's
"Characterization before extraction": the suite below asserts what
`parse_sage_coa` does TODAY — including four misclassifications — so that the
extraction of `classify_sage_category` can be proven behaviour-preserving
before any fix lands. Every knowingly-wrong assertion is tagged `# WRONGNESS`.

The fix is a SEPARATE commit. If you are reading this file and the WRONGNESS
assertions still stand, the fix has not landed yet.

⚠️ THE FUZZY FALLBACK IS BIDIRECTIONAL AND ORDER-DEPENDENT. `parse_sage_coa`
falls back to `if key in sage_category or sage_category in key` and `break`s on
the first hit in dict-insertion order. Both halves of that are defects:

  - the `sage_category in key` direction maps Sunnycrest's "SALES" to `cogs`,
    because "SALES" is a substring of the key "COST OF SALES". Thirteen revenue
    accounts (5000-5410) are categorised as cost of goods sold in production.
  - `break`-on-first means the answer depends on dict ORDER, not on which key
    is the best match.

⚠️ A NEGATING PREFIX IS INVISIBLE TO A SUBSTRING TEST — and this is the worst
of the four. "CURRENT LIABILITIES" is a substring of "NON-CURRENT LIABILITIES",
so Sunnycrest's long-term debt classifies as CURRENT liability. Current
liabilities are overstated and long-term understated, which moves working
capital and the current ratio in the direction a lender reads.

⚠️ TWO OF SUNNYCREST'S ELEVEN SAGE CATEGORIES MATCH NO KEY AT ALL and fall to
the `other` bucket: "COST OF GOODS SOLD" (the whole COGS block) and "DELIVERY
COSTS". That is most of production's 73 `other` rows, and it means the income
statement's COGS line has no accounts behind it even once something reads the
ledger.

NOT EVERY FUZZY MATCH IS WRONG. "STOCKHOLDERS' EQUITY" resolves to `equity`
only because of the fuzzy pass — the exact map has no such key. An exact-only
matcher would send it to the fallback. That case is why the fix tightens the
fuzzy pass rather than deleting it.
"""
from __future__ import annotations

import csv
import io

from app.services.data_migration_service import parse_sage_coa

# The eleven Sage categories present in Sunnycrest's actual COA export.
SUNNYCREST_SAGE_CATEGORIES = [
    "CURRENT ASSETS",
    "FIXED ASSETS",
    "CURRENT LIABILITIES",
    "NON-CURRENT LIABILITIES",
    "STOCKHOLDERS' EQUITY",
    "SALES",
    "COST OF GOODS SOLD",
    "ADMINISTRATIVE & SELLING EXPENSE",
    "PROVISION FOR TAXES",
    "DELIVERY COSTS",
    "OTHER INCOME & EXPENSES",
]


def _coa_csv(rows: list[tuple[str, str, str, str]]) -> bytes:
    """Build a Sage-shaped COA CSV.

    `parse_sage_coa` requires len(row) >= 13 and row[0] == "Chart of Accounts";
    it reads [9] category, [10] account_number, [11] description, [12] status.
    """
    buf = io.StringIO()
    w = csv.writer(buf)
    for category, number, description, status in rows:
        row = [""] * 13
        row[0] = "Chart of Accounts"
        row[1] = "Sunnycrest Precast"
        row[9] = category
        row[10] = number
        row[11] = description
        row[12] = status
        w.writerow(row)
    return buf.getvalue().encode("utf-8")


def _classify_via_parser(sage_category: str) -> tuple[str, float]:
    """Round-trip one category through the real parser."""
    parsed = parse_sage_coa(_coa_csv([(sage_category, "9999", "probe", "Active")]))
    assert len(parsed) == 1, f"expected 1 parsed row, got {len(parsed)}"
    return parsed[0]["bridgeable_account_type"], parsed[0]["confidence"]


class TestExactMatchesAreCorrectToday:
    """Five of the eleven hit the map exactly and are right."""

    def test_current_assets(self):
        assert _classify_via_parser("CURRENT ASSETS") == ("current_asset", 1.0)

    def test_fixed_assets(self):
        assert _classify_via_parser("FIXED ASSETS") == ("fixed_asset", 1.0)

    def test_current_liabilities(self):
        assert _classify_via_parser("CURRENT LIABILITIES") == ("current_liability", 1.0)

    def test_admin_selling_expense(self):
        assert _classify_via_parser("ADMINISTRATIVE & SELLING EXPENSE") == ("expense", 1.0)

    def test_provision_for_taxes(self):
        assert _classify_via_parser("PROVISION FOR TAXES") == ("tax_expense", 1.0)

    def test_other_income_and_expenses(self):
        assert _classify_via_parser("OTHER INCOME & EXPENSES") == ("other_income", 1.0)


class TestTheFuzzyPassIsSometimesRight:
    """The case that argues for tightening the fuzzy pass rather than deleting it."""

    def test_stockholders_equity_resolves_only_via_fuzzy(self):
        # There is no "STOCKHOLDERS' EQUITY" key; "EQUITY" is a substring of it,
        # so the `key in sage_category` direction finds it. Correct answer,
        # reached by the mechanism that is wrong elsewhere.
        assert _classify_via_parser("STOCKHOLDERS' EQUITY") == ("equity", 0.7)


class TestTheFourMisclassifications:
    """⚠️ WRONGNESS — every assertion in this class pins a defect."""

    def test_sales_becomes_cogs(self):
        # WRONGNESS: "SALES" in "COST OF SALES" via the `sage_category in key`
        # direction. Should be `revenue`. Thirteen production accounts.
        assert _classify_via_parser("SALES") == ("cogs", 0.7)

    def test_non_current_liabilities_becomes_current(self):
        # WRONGNESS: the negating "NON-" prefix is invisible to a substring
        # test. Should be `long_term_liability` — which already exists as a
        # value in SAGE_CATEGORY_MAP, keyed to "LONG TERM LIABILITIES".
        assert _classify_via_parser("NON-CURRENT LIABILITIES") == ("current_liability", 0.7)

    def test_cost_of_goods_sold_falls_through(self):
        # WRONGNESS: matches no key in either direction. Should be `cogs`.
        # This is the whole COGS block landing in `other`.
        assert _classify_via_parser("COST OF GOODS SOLD") == ("other", 0.0)

    def test_delivery_costs_falls_through(self):
        # WRONGNESS: no key, no fuzzy hit. Should be its own category.
        assert _classify_via_parser("DELIVERY COSTS") == ("other", 0.0)


class TestParserMechanics:
    """Behaviour that is not about classification but must survive the extraction."""

    def test_sage_category_is_preserved_verbatim_on_the_parsed_row(self):
        parsed = parse_sage_coa(_coa_csv([("SALES", "5010", "PRECAST SALES", "Active")]))
        assert parsed[0]["sage_category"] == "SALES"

    def test_category_is_uppercased_before_matching(self):
        assert _classify_via_parser("current assets") == ("current_asset", 1.0)

    def test_duplicate_account_numbers_are_dropped(self):
        parsed = parse_sage_coa(
            _coa_csv(
                [
                    ("CURRENT ASSETS", "1010", "CASH", "Active"),
                    ("CURRENT ASSETS", "1010", "CASH AGAIN", "Active"),
                ]
            )
        )
        assert len(parsed) == 1
        assert parsed[0]["description"] == "CASH"

    def test_non_numeric_account_numbers_are_skipped(self):
        parsed = parse_sage_coa(_coa_csv([("CURRENT ASSETS", "TOTAL", "not an account", "Active")]))
        assert parsed == []

    def test_inactive_rows_are_parsed_and_status_is_lowercased(self):
        # The parser does NOT filter by status — the caller does.
        parsed = parse_sage_coa(_coa_csv([("CURRENT ASSETS", "1010", "CASH", "Inactive")]))
        assert len(parsed) == 1
        assert parsed[0]["status"] == "inactive"

    def test_all_eleven_sunnycrest_categories_parse_without_error(self):
        rows = [(cat, str(1000 + i), f"acct {i}", "Active")
                for i, cat in enumerate(SUNNYCREST_SAGE_CATEGORIES)]
        parsed = parse_sage_coa(_coa_csv(rows))
        assert len(parsed) == len(SUNNYCREST_SAGE_CATEGORIES)
