"""LEDGER-1 A-1 — the AI taxonomy resolves into the canonical one.

⚠️ TWO TAXONOMIES, ONE COLUMN, AND UNTIL r174 NOTHING NOTICED.
`accounting_analysis_service.PLATFORM_CATEGORIES` was keyed
`revenue / ar / cogs / ap / expenses` — a set that cannot express a balance
sheet — while `tenant_gl_mappings.platform_category` held the Sage importer's
balance-sheet vocabulary. The column was `String(100)` with no enum, no FK and
no CHECK, so both could write to it and neither could collide.

⚠️ AND THE AI WAS ASKED FOR THE WRONG LEVEL. The prompt says
"platform_category (from lists above)", where the lists are SUBCATEGORIES
(`vault_sales`, `direct_labor`, `rent`). `vault_accounting.confirm_classification`
wrote that value straight into the mapping row. Since r174 constrains the
column, an unresolved subcategory would raise IntegrityError on a path that has
never been exercised — `tenant_accounting_analysis` holds 0 rows on every
database. Latent, not live, and closed here before it could become live.

The subcategories are KEPT, deliberately. `vault_sales` versus `urn_sales` is
real operational information that `revenue` throws away. They resolve to a
canonical parent on write rather than being flattened at the source.
"""
from __future__ import annotations

import pytest

from app.services.accounting_analysis_service import (
    PLATFORM_CATEGORIES,
    resolve_platform_category,
)
from app.services.data_migration_service import PLATFORM_ACCOUNT_CATEGORIES


class TestTheTaxonomiesAreReconciled:

    def test_every_key_is_a_canonical_category(self):
        outside = set(PLATFORM_CATEGORIES) - set(PLATFORM_ACCOUNT_CATEGORIES)
        assert outside == set(), f"keys outside the canonical vocabulary: {outside}"

    def test_the_old_non_canonical_keys_are_gone(self):
        # `ar` named a subledger, not a statement line; AR is a current asset.
        # `ap` likewise. `expenses` was a plural that matched nothing.
        for dead in ("ar", "ap", "expenses"):
            assert dead not in PLATFORM_CATEGORIES

    def test_no_subcategory_is_claimed_by_two_parents(self):
        seen: dict[str, str] = {}
        for parent, subs in PLATFORM_CATEGORIES.items():
            for sub in subs:
                assert sub not in seen, f"{sub!r} under both {seen.get(sub)!r} and {parent!r}"
                seen[sub] = parent


class TestResolution:

    def test_a_canonical_category_passes_through(self):
        for category in PLATFORM_ACCOUNT_CATEGORIES:
            assert resolve_platform_category(category) == category

    def test_a_subcategory_resolves_to_its_parent(self):
        for parent, subs in PLATFORM_CATEGORIES.items():
            for sub in subs:
                assert resolve_platform_category(sub) == parent

    @pytest.mark.parametrize(
        "sub,parent",
        [
            ("vault_sales", "revenue"),
            ("accounts_payable", "current_liability"),
            ("ar_funeral_homes", "current_asset"),
            ("delivery_costs", "delivery_cost"),
            ("interest_expense", "other_expense"),
            ("gain_on_sale", "other_income"),
        ],
    )
    def test_the_interesting_resolutions(self, sub, parent):
        assert resolve_platform_category(sub) == parent

    def test_case_and_whitespace_are_tolerated(self):
        assert resolve_platform_category("  Vault_Sales  ") == "revenue"

    def test_an_unknown_value_returns_none_rather_than_guessing(self):
        # None is what lets the caller raise a 400 instead of letting a CHECK
        # constraint surface as a 500.
        assert resolve_platform_category("not_a_category") is None

    def test_empty_and_none_return_none(self):
        assert resolve_platform_category(None) is None
        assert resolve_platform_category("") is None

    def test_resolution_is_total_over_the_coa_template_endpoint(self):
        # `GET .../coa-template` emits platform_category=<subcategory>. A client
        # feeding that back into confirm_classification must not hit the
        # constraint, so every emitted value has to resolve.
        for subs in PLATFORM_CATEGORIES.values():
            for sub in subs:
                assert resolve_platform_category(sub) is not None


class TestTheWriteBoundaryRefuses:

    def test_the_handler_resolves_before_writing(self):
        # Pinning the wiring, not the HTTP: confirm_classification must call the
        # resolver rather than assigning the raw suggestion. If this import or
        # the call disappears, an unresolved subcategory reaches the constraint.
        import inspect

        from app.api.routes import vault_accounting

        src = inspect.getsource(vault_accounting.confirm_classification)
        assert "resolve_platform_category(" in src, (
            "confirm_classification no longer resolves — an AI subcategory "
            "would reach the r174 CHECK constraint as a 500"
        )
        assert "row.platform_category = chosen" in src
