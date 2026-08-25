"""LEDGER-1 A-1 — characterization of the Sage COA category classifier.

⚠️ THESE TESTS PIN BEHAVIOUR THAT IS WRONG, ON PURPOSE. Per CLAUDE.md's
"Characterization before extraction": the suite below asserts what
`parse_sage_coa` does TODAY — including four misclassifications — so that the
extraction of `classify_sage_category` can be proven behaviour-preserving
before any fix lands. Every knowingly-wrong assertion is tagged `# WRONGNESS`.

The fix landed in the commit after the extraction; the WRONGNESS assertions
below have been flipped to assert the corrected behaviour, and the history of
what they used to pin is kept in each test's comment.

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

    def test_stockholders_equity_is_now_an_exact_key(self):
        # Pre-fix this resolved via the fuzzy pass at 0.7 — correct answer,
        # reached by the mechanism that was wrong elsewhere. The fix adds the
        # exact key, so it is now 1.0. The fuzzy pass is KEPT because this case
        # is why: deleting it would have lost a correct answer.
        assert _classify_via_parser("STOCKHOLDERS' EQUITY") == ("equity", 1.0)

    def test_forward_fuzzy_still_resolves_an_unmapped_variant(self):
        # The generalised STOCKHOLDERS case: a label that CONTAINS a key still
        # resolves, at 0.7, with no exact key of its own.
        assert _classify_via_parser("TOTAL FIXED ASSETS") == ("fixed_asset", 0.7)


class TestTheFourMisclassificationsAreFixed:
    """Each of these pinned a defect before the fix; each now asserts the cure."""

    def test_sales_is_revenue(self):
        # WAS: ("cogs", 0.7) — "SALES" is a substring of the key "COST OF
        # SALES", and the fuzzy pass matched in that direction. Thirteen
        # production accounts (5000-5410) carry `cogs` because of this.
        assert _classify_via_parser("SALES") == ("revenue", 1.0)

    def test_non_current_liabilities_is_long_term(self):
        # WAS: ("current_liability", 0.7) — the negating "NON-" prefix was
        # invisible to a substring test, so long-term debt classified as
        # current. Overstated current liabilities, understated long-term.
        assert _classify_via_parser("NON-CURRENT LIABILITIES") == ("long_term_liability", 1.0)

    def test_cost_of_goods_sold_is_cogs(self):
        # WAS: ("other", 0.0) — matched no key in either direction. The whole
        # COGS block was landing in the `other` bucket.
        assert _classify_via_parser("COST OF GOODS SOLD") == ("cogs", 1.0)

    def test_delivery_costs_is_its_own_category(self):
        # WAS: ("other", 0.0). `delivery_cost` is deliberately not folded into
        # `cogs`: licensees differ in whether hauling is outsourced or run
        # in-house, and gross margin has to mean the same thing across them.
        assert _classify_via_parser("DELIVERY COSTS") == ("delivery_cost", 1.0)


class TestTheThreeFuzzyMechanisms:
    """Each defect fixed independently, probed where no exact key applies."""

    def test_reverse_direction_is_gone(self):
        # Pre-fix, "TAXES" matched the key "PROVISION FOR TAXES" via
        # `sage_category in key` and returned tax_expense — accidentally right.
        # That direction is removed: a category is matched by a key it
        # CONTAINS, never by a key that contains it. Refusing is the point.
        assert _classify_via_parser("TAXES") == ("unclassified", 0.0)

    def test_negation_guard_rejects_an_inverted_prefix(self):
        # "CURRENT ASSETS" is a substring of "LESS CURRENT ASSETS"; the prefix
        # inverts the meaning, so the match is refused rather than guessed.
        assert _classify_via_parser("LESS CURRENT ASSETS") == ("unclassified", 0.0)

    def test_longest_key_wins_not_dict_order(self):
        # "TOTAL NON-CURRENT LIABILITIES" contains BOTH "CURRENT LIABILITIES"
        # (19 chars, earlier in the map) and "NON-CURRENT LIABILITIES" (23,
        # later). Pre-fix, break-on-first returned the shorter, earlier key —
        # current_liability. Longest-match returns the specific one.
        #
        # This probe was chosen deliberately: an earlier version used "OTHER
        # CURRENT LIABILITIES", which passes against the PRE-fix code too and
        # therefore proves nothing about the ordering change.
        assert _classify_via_parser("TOTAL NON-CURRENT LIABILITIES") == ("long_term_liability", 0.7)

    def test_unmapped_returns_unclassified_not_other(self):
        # `other` means a human judged the account miscellaneous.
        # `unclassified` means the importer could not map it. Distinct on
        # purpose — collapsing them is how 73 of 224 accounts became
        # indistinguishable from a deliberate choice.
        got, confidence = _classify_via_parser("SOMETHING SAGE HAS NEVER EMITTED")
        assert got == "unclassified"
        assert confidence == 0.0


class TestTheVocabulary:

    def test_every_mapped_value_is_in_the_canonical_set(self):
        from app.services.data_migration_service import (
            PLATFORM_ACCOUNT_CATEGORIES,
            SAGE_CATEGORY_MAP,
        )
        unknown = set(SAGE_CATEGORY_MAP.values()) - PLATFORM_ACCOUNT_CATEGORIES
        assert unknown == set(), f"map emits values outside the vocabulary: {unknown}"

    def test_the_fallback_is_in_the_canonical_set(self):
        from app.services.data_migration_service import (
            PLATFORM_ACCOUNT_CATEGORIES,
            UNCLASSIFIED,
        )
        assert UNCLASSIFIED in PLATFORM_ACCOUNT_CATEGORIES

    def test_contra_revenue_exists_but_is_not_reachable_from_a_sage_category(self):
        # Sage files refunds, returns, rebates and cash discounts inside SALES
        # alongside gross revenue, so contra_revenue cannot be derived from the
        # category. It is applied per-account after import.
        from app.services.data_migration_service import (
            PLATFORM_ACCOUNT_CATEGORIES,
            SAGE_CATEGORY_MAP,
        )
        assert "contra_revenue" in PLATFORM_ACCOUNT_CATEGORIES
        assert "contra_revenue" not in set(SAGE_CATEGORY_MAP.values())

    def test_all_eleven_sunnycrest_categories_map_without_falling_back(self):
        for category in SUNNYCREST_SAGE_CATEGORIES:
            got, confidence = _classify_via_parser(category)
            assert got != "unclassified", f"{category} fell through to the fallback"
            assert confidence == 1.0, f"{category} resolved at {confidence}, expected an exact key"


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
