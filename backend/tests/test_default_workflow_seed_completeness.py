"""D-4 — seed-omission class killed at the mechanism (audit C-5/C-6/C-7).

`seed_default_workflows` upserts ONLY keys present in the seed dicts
(deliberate — protects customized values). The consequence: an omitted
ownership-critical key is never corrected in any environment. That is how
`wf_sys_cash_receipts` sat misfiled at scope='tenant' everywhere and the
three migrated agents kept stale `agent_registry_key` badges for months.

These tests walk the seed dicts and pin the ownership-critical keys as
PRESENT and coherent — so the class can't recur when the next seed entry
gets written. Plus query-construction pins for the two seed scripts that
crashed on every deploy against renamed model attributes.
"""
from __future__ import annotations

import pytest

from app.data.default_workflows import ALL_DEFAULT_WORKFLOWS
from app.database import SessionLocal
from app.models.workflow import Workflow


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.rollback()
    s.close()


class TestOwnershipKeysDeclared:
    def test_every_entry_declares_scope(self):
        missing = [w["id"] for w in ALL_DEFAULT_WORKFLOWS if "scope" not in w]
        assert missing == [], (
            f"Seed dicts missing explicit 'scope': {missing}. The upsert only "
            f"touches keys present in the dict — an omitted scope is never "
            f"corrected in any environment (this is how wf_sys_cash_receipts "
            f"was misfiled as 'tenant' everywhere)."
        )

    def test_scope_matches_tier_and_vertical(self):
        """Mirror of the r36 + r38 derivation: tier 1 cross-vertical = core;
        tier 1 vertical-specific = vertical; tier 2/3 = vertical."""
        for w in ALL_DEFAULT_WORKFLOWS:
            expected = "core" if (w["tier"] == 1 and not w.get("vertical")) else "vertical"
            assert w["scope"] == expected, (
                f"{w['id']}: scope={w['scope']!r} but tier={w['tier']} "
                f"vertical={w.get('vertical')!r} implies {expected!r}"
            )

    def test_every_tier1_entry_declares_agent_registry_key(self):
        """Explicit even when None — so a DB carrying a stale key from before
        an agent-to-workflow migration gets corrected on the next seed run
        (the 'Built-in implementation' badge class)."""
        missing = [
            w["id"] for w in ALL_DEFAULT_WORKFLOWS
            if w["tier"] == 1 and "agent_registry_key" not in w
        ]
        assert missing == [], f"Tier-1 seed dicts missing explicit agent_registry_key: {missing}"

    def test_declared_keys_survive_the_upsert_whitelist(self):
        """seed_workflows silently DROPS dict keys that aren't Workflow
        columns. If scope/agent_registry_key ever get renamed on the model,
        the declarations would silently stop applying — fail loud instead."""
        cols = {c.name for c in Workflow.__table__.columns}
        assert "scope" in cols
        assert "agent_registry_key" in cols


class TestSeedScriptsQueryRealColumns:
    """The C-7 class: seed_quotes / seed_saved_orders crashed on EVERY deploy
    for months (warn-and-continue tier) against renamed model attributes
    (CompanyModule.module_key/.is_enabled; Workflow.workflow_key). Execute the
    actual query-construction paths so a future rename fails HERE, not in the
    deploy log."""

    def test_seed_quotes_tenant_pick_executes(self, db):
        from scripts.seed_quotes import pick_tenant
        pick_tenant(db)  # must not raise (None result is fine)

    def test_seed_saved_orders_picks_execute(self, db):
        from scripts.seed_saved_orders import pick_tenant, pick_workflow
        pick_tenant(db)
        pick_workflow(db, "no-such-company")  # exercises the wf_compose + fallback queries
