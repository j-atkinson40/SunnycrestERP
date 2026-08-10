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


class TestRawSqlIdentifiersExist:
    """Every table and column in the seed's raw SQL must exist in the models.

    THE SCHEMA IS NOT GUESSABLE AND THIS COST A PRODUCTION WRITE. The cleanup
    said `journal_entry_lines.entry_id`; the column is `journal_entry_id`, and
    `entry` is merely what the RELATIONSHIP is called. A second latent one sat
    beside it — `journal_entries.company_id`, where this schema uses
    `tenant_id`. Both were invisible until executed, and a raw-SQL DELETE is
    exactly where that costs most: the statement is only checked when it runs,
    and by then it is running against production.

    Static, no DB — reads `Base.metadata`, which the models populate on import.
    """

    def _statements(self) -> list[str]:
        import pathlib
        import re
        src = pathlib.Path(
            __file__
        ).resolve().parents[1] / "scripts" / "seed_accounting_demo.py"
        text = src.read_text()
        # The raw SQL lives inside text("...") calls, often concatenated across
        # adjacent string literals — join them before parsing.
        return [
            " ".join(re.findall(r'"([^"]*)"', block))
            for block in re.findall(r"text\(\s*((?:\s*\"[^\"]*\"\s*)+)\)", text)
        ]

    def test_every_referenced_table_and_column_exists(self):
        import re

        import app.models  # noqa: F401  — populates the metadata
        from app.database import Base

        tables = Base.metadata.tables
        problems: list[str] = []

        for stmt in self._statements():
            # `LATERAL` is a keyword, not a table — without skipping it the
            # scan reports a phantom unknown table and, worse, ABORTS before
            # checking that statement's columns. A guard that bails on its own
            # false positive is a guard that silently stops guarding.
            refs = {
                m.lower() for m in re.findall(
                    r"\b(?:FROM|INTO|UPDATE|JOIN)\s+(?:LATERAL\s+)?([a-z_][a-z0-9_]*)",
                    stmt, re.I,
                )
            } - {"lateral"}
            # `alembic_version` is real but Alembic owns it, so it is absent
            # from the app's metadata. Named rather than silently skipped.
            unknown = [t for t in refs
                       if t not in tables and t != "alembic_version"]
            refs -= {"alembic_version"}
            if unknown:
                problems.append(f"unknown table(s) {unknown} in: {stmt[:70]}…")
                continue
            if not refs:
                continue
            # Derived names introduced by `... AS alias` are legitimate and are
            # not columns of anything. Collected rather than ignored, so the
            # check stays strict about names that ARE claimed to be columns.
            aliases = {a.lower() for a in re.findall(r"\bAS\s+([a-z_][a-z0-9_]*)",
                                                     stmt, re.I)}
            known_cols = {c.name for t in refs for c in tables[t].columns} | aliases
            # Identifiers used in a comparison — `col = ANY(:x)`, `col = :x`,
            # `col IS NULL`, `col LIKE '...'`. These are where a wrong name hides.
            used = set(re.findall(
                r"\b([a-z_][a-z0-9_]*)\s*(?:=\s*(?:ANY\(|:)|IS\s+(?:NOT\s+)?NULL|LIKE\s)",
                stmt, re.I,
            ))
            for col in used - known_cols:
                if col.upper() in {"AND", "OR", "WHERE", "NOT", "SELECT", "NULL"}:
                    continue
                problems.append(
                    f"column {col!r} not on {sorted(refs)} in: {stmt[:70]}…"
                )

        assert not problems, "raw SQL references identifiers that do not exist:\n  " + \
            "\n  ".join(problems)


class TestDeleteOrderRespectsTheConstraintGraph:
    """The cleanup's delete order must satisfy the FK graph, DERIVED not reasoned.

    Hand-ordering failed twice in one function. `reconciliation_transactions`
    was accounted for and `customer_payments` was not — both hold non-cascading
    pointers into `journal_entries`, and the second only surfaced when the
    database refused it mid-delete on production. Reasoning about which table
    "depends on" which is what produced the wrong answer; the constraint graph
    is the only thing that knows.

    This asserts the property rather than the current order, so a NEW reference
    added to `journal_entries` fails here instead of during a delete.
    """

    def _delete_sequence(self) -> list[str]:
        import pathlib
        import re
        src = pathlib.Path(
            __file__
        ).resolve().parents[1] / "scripts" / "seed_accounting_demo.py"
        body = src.read_text().split("ORDER IS THE CONTRACT")[-1]
        return re.findall(r"DELETE FROM ([a-z_]+)", body)

    def test_children_are_deleted_before_their_parents(self):
        import app.models  # noqa: F401
        from app.database import Base

        seq = self._delete_sequence()
        assert seq, "no delete sequence found"
        position = {t: i for i, t in enumerate(seq)}

        problems = []
        for table in Base.metadata.tables.values():
            for fk in table.foreign_keys:
                child, parent = table.name, fk.column.table.name
                # A cascading FK needs no ordering — the database handles it.
                if (fk.ondelete or "").upper() == "CASCADE":
                    continue
                if child in position and parent in position:
                    if position[child] > position[parent]:
                        problems.append(
                            f"{child}.{fk.parent.name} -> {parent}: {child} is "
                            f"deleted AFTER {parent}, so the FK will refuse"
                        )
        assert not problems, "delete order violates the FK graph:\n  " + \
            "\n  ".join(sorted(set(problems)))


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
        parts = _EXPECTED["cleared"] + _EXPECTED["ranked"] + \
            _EXPECTED["coding"] + _EXPECTED["blocked"]
        assert parts == _EXPECTED["lines"], (
            f"card forms sum to {parts}, not {_EXPECTED['lines']} — every line "
            f"lands in exactly one form, so a gap means one is unaccounted for"
        )

    def test_ranked_cards_are_asserted_at_all(self):
        """The property the first table LACKED.

        It checked `needs_human`, which folded ranked and coding together — so a
        queue of twenty coding cards scored identically to the designed mix, and
        it passed a run whose ranked cards were the open question. `ranked` is
        the number that fails that run and passes this one.
        """
        assert _EXPECTED["ranked"] > 0, (
            "with ranked=0 the table cannot tell a working queue from one where "
            "every card is a coding card — which is the failure it exists for"
        )

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
        needs_human = _EXPECTED["ranked"] + _EXPECTED["coding"] + _EXPECTED["blocked"]
        assert needs_human > _EXPECTED["cleared"]
        assert 10 <= needs_human <= 40

    def test_only_keyword_lines_match_the_keyword_ladder(self):
        """THE LADDER RUNS BEFORE CANDIDATE MATCHING.

        A description decides whether a line is scored against an amount at all.
        The first production run lost a band card because "DEPOSIT ACH RETURNED
        ITEM ADJ" hit the nsf rung on the word RETURNED — written for
        plausibility, never checked against the vocabulary. The symptom was a
        candidate that silently never appeared, which reads as a matcher bug.

        Read from `_KEYWORD_LADDER`, not restated, so a rung added later fails
        here rather than in a demo.
        """
        from app.services.reconciliation_service import _KEYWORD_LADDER

        for label, _o, _amt, description, _r in _FEED_LINES:
            hit = next(
                (c for c, _conf, kws in _KEYWORD_LADDER
                 if any(kw in description.upper() for kw in kws)),
                None,
            )
            if label.startswith("keyword_"):
                assert hit is not None, (
                    f"{label} is a keyword line but {description!r} matches no "
                    f"rung — it would fall through to candidate matching"
                )
            else:
                assert hit is None, (
                    f"{label}: {description!r} matches the {hit!r} rung and would "
                    f"be blocked before its amount is compared"
                )

    def test_matched_lines_are_dated_to_meet_the_payment_window(self):
        """Auto/band/collision lines sit AT the statement date, and phase 3
        dates their payments ≤4 days earlier — inside DATE_WINDOW_DAYS (5) by
        construction. The first production run had gaps of 6, 9 and 20 days
        because the two were computed independently."""
        from app.services.reconciliation_service import DATE_WINDOW_DAYS

        assert max(p[2] for p in _PAYMENTS) < DATE_WINDOW_DAYS, (
            "a payment is dated further back than the matching window allows; "
            "phase 4's matched lines sit at the statement date"
        )

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
