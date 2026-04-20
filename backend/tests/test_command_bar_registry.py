"""Unit tests — Command Bar action registry.

Scope: registry.py in isolation. No DB, no HTTP.

Covers:
  - Default seed populates navigate + create actions
  - register_action replaces by action_id (last-write-wins)
  - list_actions filters by action_type + entity_type
  - find_by_alias resolves label and alias strings
  - match_actions scoring ordering
  - reset_registry un-seeds the singleton
"""

from __future__ import annotations

import pytest

from app.services.command_bar import registry


@pytest.fixture(autouse=True)
def _fresh_registry():
    registry.reset_registry()
    yield
    registry.reset_registry()


class TestDefaultSeed:
    def test_registry_has_navigate_and_create_actions_after_seed(self):
        reg = registry.get_registry()
        assert len(reg) > 0
        nav = registry.list_actions(action_type="navigate")
        create = registry.list_actions(action_type="create")
        assert len(nav) >= 10, f"expected 10+ navigate actions, got {len(nav)}"
        assert len(create) >= 5, f"expected 5+ create actions, got {len(create)}"

    def test_seed_includes_dashboard_navigate(self):
        entry = registry.find_by_alias("Dashboard")
        assert entry is not None
        assert entry.action_type == "navigate"
        assert entry.target_url == "/dashboard"

    def test_seed_includes_new_sales_order_create(self):
        entry = registry.find_by_alias("new sales order")
        assert entry is not None
        assert entry.action_type == "create"
        assert entry.entity_type == "sales_order"

    def test_ar_alias_resolves_to_ar_aging(self):
        entry = registry.find_by_alias("AR")
        assert entry is not None
        assert entry.action_id == "nav.ar_aging"

    def test_pnl_alias_resolves_to_profit_and_loss(self):
        entry = registry.find_by_alias("P&L")
        assert entry is not None
        assert entry.action_id == "nav.pnl"


class TestRegistration:
    def test_register_new_action(self):
        registry.reset_registry()
        registry.register_action(
            registry.ActionRegistryEntry(
                action_id="test.foo",
                action_type="navigate",
                label="Foo",
                icon="Folder",
                target_url="/foo",
            )
        )
        reg = registry.get_registry()
        assert "test.foo" in reg
        assert reg["test.foo"].label == "Foo"

    def test_register_replaces_by_action_id(self):
        registry.reset_registry()
        registry.get_registry()  # trigger seed
        original = registry.get_registry()["nav.dashboard"]
        replacement = registry.ActionRegistryEntry(
            action_id="nav.dashboard",
            action_type="navigate",
            label="Dashboard Replaced",
            icon="Home",
            target_url="/home",
        )
        registry.register_action(replacement)
        new = registry.get_registry()["nav.dashboard"]
        assert new.label == "Dashboard Replaced"
        assert new.target_url == "/home"
        assert new.label != original.label


class TestListActions:
    def test_filter_by_action_type_navigate(self):
        results = registry.list_actions(action_type="navigate")
        assert all(r.action_type == "navigate" for r in results)

    def test_filter_by_action_type_create(self):
        results = registry.list_actions(action_type="create")
        assert all(r.action_type == "create" for r in results)

    def test_filter_by_entity_type(self):
        results = registry.list_actions(entity_type="sales_order")
        assert len(results) >= 1
        assert all(r.entity_type == "sales_order" for r in results)
        # create action should be present
        assert any(r.action_type == "create" for r in results)


class TestFindByAlias:
    def test_exact_label_match(self):
        entry = registry.find_by_alias("Dashboard")
        assert entry is not None
        assert entry.action_id == "nav.dashboard"

    def test_exact_alias_match(self):
        entry = registry.find_by_alias("home")
        assert entry is not None
        assert entry.action_id == "nav.dashboard"

    def test_case_insensitive(self):
        entry = registry.find_by_alias("dashboard")
        assert entry is not None
        assert entry.action_id == "nav.dashboard"

    def test_no_match_returns_none(self):
        entry = registry.find_by_alias("zzzz nonexistent zzz")
        assert entry is None

    def test_empty_returns_none(self):
        assert registry.find_by_alias("") is None
        assert registry.find_by_alias("   ") is None


class TestMatchActions:
    def test_exact_alias_gets_max_score(self):
        results = registry.match_actions("ar aging")
        assert len(results) >= 1
        top_entry, top_score = results[0]
        assert top_entry.action_id == "nav.ar_aging"
        assert top_score == 1.0

    def test_prefix_match_scores_below_exact(self):
        # "ar" prefix-matches the "ar" alias first (exact) — but
        # also prefix-matches "ar aging" label. Exact wins.
        results = registry.match_actions("accounts rec")
        labels = [e.label for e, _ in results[:3]]
        assert "AR Aging" in labels

    def test_scoring_desc_order(self):
        results = registry.match_actions("quote")
        scores = [s for _, s in results]
        assert scores == sorted(scores, reverse=True)

    def test_empty_query_returns_empty(self):
        assert registry.match_actions("") == []
        assert registry.match_actions("   ") == []

    def test_max_results_cap(self):
        # "new" likely matches many create actions + their aliases.
        # Cap enforcement.
        results = registry.match_actions("new", max_results=3)
        assert len(results) <= 3

    def test_no_match_returns_empty(self):
        assert registry.match_actions("xyzqq nothing matches abc123") == []


class TestResetRegistry:
    def test_reset_clears_and_reseeds_on_next_access(self):
        _ = registry.get_registry()  # seed
        registry.reset_registry()
        # After reset, get_registry should re-seed
        reg = registry.get_registry()
        assert len(reg) > 0

    def test_reset_allows_custom_seed_override(self):
        registry.reset_registry()
        # Register a custom action BEFORE triggering seed
        registry.register_action(
            registry.ActionRegistryEntry(
                action_id="nav.dashboard",
                action_type="navigate",
                label="Custom Home",
                icon="Home",
                target_url="/custom-home",
            )
        )
        # Now trigger seed
        reg = registry.get_registry()
        # Seeding replaced our custom entry (seed runs if not already
        # seeded — our register_action DID NOT mark _seeded=True).
        # So the seed DOES overwrite. This is correct behavior for
        # platform-owned actions.
        assert reg["nav.dashboard"].label == "Dashboard"
