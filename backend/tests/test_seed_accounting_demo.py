"""DEMO-2 seed — the design invariants, guarded statically.

PURE STATIC. No DB, no imports of the app's session — these read the seed's own
tables and check that the numbers agree with each other. That is deliberate: the
seed's money is HAND-COMPUTED, and the thing worth guarding is that the literals
and the arithmetic beside them have not drifted apart. A test that recomputed the
totals from the line items would agree with any typo that appeared in both.

The phase-4 population is checked the same way. Its first execution will be
against production; until then these are the only thing standing between a
designed ratio and a plausible-looking one.
"""
from __future__ import annotations

from collections import Counter
from decimal import Decimal

from scripts.seed_accounting_demo import (
    _BILLS,
    _EXPECTED,
    _FEED_LINES,
    _INVOICES,
    _PAYMENTS,
)


class TestMoneyMath:
    def test_invoice_totals_match_their_line_arithmetic(self):
        """Each hand-proved total equals Σ(qty × unit) for its lines.

        This is the ONE place recomputation is legitimate: the literal was
        written by hand and the arithmetic is being checked against it, not
        derived from it. A mismatch means the comment and the number disagree.
        """
        for acct, days, lines, expected in _INVOICES:
            computed = sum(Decimal(str(q)) * Decimal(u) for _sku, q, u in lines)
            assert computed == expected, (
                f"{acct} d-{days}: lines compute {computed}, literal says {expected}"
            )

    def test_bill_totals_match_their_line_arithmetic(self):
        for acct, days, lines, expected in _BILLS:
            computed = sum(Decimal(str(q)) * Decimal(u) for _d, q, u in lines)
            assert computed == expected, (
                f"{acct} d-{days}: lines compute {computed}, literal says {expected}"
            )

    def test_applied_never_exceeds_the_payment(self):
        """`create_customer_payment` raises 400 when applications exceed the
        payment. A seed that tripped it would fail at run time on production."""
        for label, _inv, _days, amount, applied, _method in _PAYMENTS:
            assert applied <= amount, f"{label}: applies {applied} of {amount}"

    def test_the_overpayment_actually_overpays(self):
        """The credit pocket needs an unapplied excess to have anything in it."""
        row = next(p for p in _PAYMENTS if p[0] == "overpayment")
        _label, _inv, _days, amount, applied, _m = row
        # 1750.00 − 1500.00 = 250.00 into the pocket.
        assert amount - applied == Decimal("250.00")


class TestPhase3Phase4Coupling:
    """The coupling neither spec stated, pinned so editing one phase in
    isolation fails here rather than silently in the matcher."""

    def test_a_duplicate_amount_pair_exists_for_the_collision(self):
        amounts = Counter(p[3] for p in _PAYMENTS)
        dupes = [a for a, n in amounts.items() if n >= 2]
        assert dupes, (
            "no two payments share an amount — phase 4's collision line would "
            "have a single viable exact match and would AUTO-CLEAR, so the "
            "ambiguity it exists to demonstrate would never reach the queue."
        )

    def test_the_collision_line_matches_the_duplicated_amount(self):
        amounts = Counter(p[3] for p in _PAYMENTS)
        duplicated = {a for a, n in amounts.items() if n >= 2}
        collision = next(l for l in _FEED_LINES if l[0] == "collision")
        assert collision[2] in duplicated, (
            f"collision line is {collision[2]}, which no pair of payments shares"
        )

    def test_auto_clear_lines_are_backed_by_exactly_one_payment_each(self):
        """An auto-clear needs `len(viable_exact) == 1`. A line whose amount
        matches zero payments becomes a coding card; one matching two becomes a
        ranked card. Either way the expected-outcome table would be wrong."""
        amounts = Counter(p[3] for p in _PAYMENTS)
        for label, _d, amount, _desc, _ref in _FEED_LINES:
            if not label.startswith("auto_"):
                continue
            assert amounts[amount] == 1, (
                f"{label} at {amount} matches {amounts[amount]} payments; "
                f"auto-clear requires exactly one."
            )


class TestPhase4Population:
    def test_the_expected_table_adds_up(self):
        assert _EXPECTED["lines"] == len(_FEED_LINES)
        assert _EXPECTED["auto_cleared"] + _EXPECTED["needs_human"] == _EXPECTED["lines"]

    def test_the_collision_line_carries_no_reference_number(self):
        """LOAD-BEARING BLANK. With a reference set, the matcher's
        `elif txn.reference_number` fallback finds one of the two candidates by
        reference and auto-accepts it at 0.97. A later reader seeing an empty
        field will want to fill it; this is what says don't."""
        collision = next(l for l in _FEED_LINES if l[0] == "collision")
        assert collision[4] is None

    def test_exactly_one_line_books_a_keyword_and_one_refuses(self):
        descs = [l[3].upper() for l in _FEED_LINES]
        assert sum("SERVICE CHARGE" in d for d in descs) == 1
        assert sum("PAYROLL" in d for d in descs) == 1

    def test_the_queue_is_not_a_rounding_error(self):
        """W-2 ended at 95.8% auto-match with an empty workspace. The demo
        teaches the QUEUE, so the exceptions must dominate — and must stay in
        the low tens, because three teaches no rhythm and four hundred is
        unreviewable."""
        assert _EXPECTED["needs_human"] > _EXPECTED["auto_cleared"]
        assert 10 <= _EXPECTED["needs_human"] <= 40

    def test_feed_line_labels_are_unique(self):
        """Labels become `plaid_transaction_id` marker suffixes; a duplicate
        would make the second line idempotently skip the first's row."""
        labels = [l[0] for l in _FEED_LINES]
        assert len(labels) == len(set(labels))

    def test_money_in_is_positive_and_money_out_is_negative(self):
        """`populate_from_feed` derives transaction_type from the sign:
        positive → credit. A payment-matching line MUST be positive or it is
        typed as a debit and matches nothing."""
        for label, _d, amount, _desc, _ref in _FEED_LINES:
            if label.startswith(("auto_", "band_", "collision")):
                assert amount > 0, f"{label} must be money IN to match a payment"
        fee = next(l for l in _FEED_LINES if l[0] == "keyword_fee")
        payroll = next(l for l in _FEED_LINES if l[0] == "keyword_payroll")
        assert fee[2] < 0 and payroll[2] < 0
