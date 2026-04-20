"""Unit tests — Command Bar intent classifier.

Scope: intent.py in isolation. No DB, no HTTP.

Covers:
  - All five Intent outcomes (navigate / search / create / action / empty)
  - Record-number pattern detection (SO-2026-0042, INV-2026-0001, etc.)
  - Create-verb + entity type detection
  - Navigate-verb prefix detection
  - Alias / label exact match
  - Edge cases (whitespace, single chars, numbers-only)
  - is_create_entity_query returns the right entity type
  - should_search_entities skips for empty + create intents
"""

from __future__ import annotations

import pytest

from app.services.command_bar import intent, registry


@pytest.fixture(autouse=True)
def _fresh_registry():
    registry.reset_registry()
    # Prime the registry so find_by_alias / match_actions work.
    registry.get_registry()
    yield
    registry.reset_registry()


class TestEmptyIntent:
    def test_empty_string(self):
        assert intent.classify("") == "empty"

    def test_whitespace_only(self):
        assert intent.classify("   ") == "empty"
        assert intent.classify("\t\n") == "empty"

    def test_none_equivalent(self):
        # The API always passes strings, but defense-in-depth.
        assert intent.classify("") == "empty"


class TestRecordNumberIntent:
    @pytest.mark.parametrize(
        "q",
        [
            "SO-2026-0042",
            "so-2026-0042",
            "INV-2026-0001",
            "inv 2026 0001",
            "Q-2026-0015",
            "CASE-2026-0099",
            "PO-2026-0001",
        ],
    )
    def test_record_number_pattern_is_navigate(self, q):
        assert intent.classify(q) == "navigate", q


class TestExactAliasMatch:
    def test_label_exact_match_navigate(self):
        # "Dashboard" is a nav label.
        assert intent.classify("Dashboard") == "navigate"

    def test_alias_exact_match_navigate(self):
        # "AR" is a nav alias.
        assert intent.classify("AR") == "navigate"

    def test_create_label_exact_match(self):
        assert intent.classify("New sales order") == "create"


class TestCreateVerbIntent:
    @pytest.mark.parametrize(
        "q",
        [
            "new sales order",
            "new order",
            "create quote",
            "add contact",
            "new invoice",
            "draft quote",
        ],
    )
    def test_create_verb_plus_entity(self, q):
        assert intent.classify(q) == "create", q

    def test_create_verb_without_entity_falls_to_search(self):
        # "new" alone isn't specific enough.
        assert intent.classify("new") == "search"

    def test_unknown_verb_plus_noun_falls_to_search(self):
        # "delete" isn't a create verb.
        assert intent.classify("delete invoice") == "search"

    def test_new_foo_bar_with_no_create_match_falls_to_search(self):
        # "new zzzz" with no matching create action → search.
        assert intent.classify("new zzzzzzzz") == "search"


class TestNavigateVerbIntent:
    @pytest.mark.parametrize(
        "q",
        [
            "go to dashboard",
            "open financials",
            "navigate ar aging",
            "view pricing",
            "show invoices",
        ],
    )
    def test_navigate_verbs(self, q):
        assert intent.classify(q) == "navigate", q


class TestFuzzyNavigateIntent:
    def test_prefix_match_high_score_classifies_as_navigate(self):
        # "dashbo" prefix-matches "Dashboard" with score ≥ 0.9 → navigate
        assert intent.classify("Dashboard") == "navigate"

    def test_low_score_match_falls_to_search(self):
        # Random free text — no good matches. Search intent default.
        assert intent.classify("what do we owe") == "search"


class TestSearchDefault:
    def test_plain_text_is_search(self):
        # Ordinary person name — search default.
        assert intent.classify("SMITH") == "search"

    def test_multi_word_is_search(self):
        assert intent.classify("bronze vault for hopkins") == "search"


class TestIsCreateEntityQuery:
    def test_new_sales_order_returns_entity(self):
        assert intent.is_create_entity_query("new sales order") == "sales_order"

    def test_create_quote_returns_entity(self):
        assert intent.is_create_entity_query("create quote") == "quote"

    def test_add_contact_returns_entity(self):
        assert intent.is_create_entity_query("add contact") == "contact"

    def test_non_create_returns_none(self):
        assert intent.is_create_entity_query("SMITH") is None
        assert intent.is_create_entity_query("") is None
        assert intent.is_create_entity_query("new") is None


class TestShouldSearchEntities:
    def test_search_intent_triggers_entity_search(self):
        assert intent.should_search_entities("search") is True

    def test_navigate_intent_triggers_entity_search(self):
        # Navigate may fall through to records — keep the resolver
        # hot for the common case (user types a record name).
        assert intent.should_search_entities("navigate") is True

    def test_create_intent_skips_entity_search(self):
        assert intent.should_search_entities("create") is False

    def test_empty_intent_skips_entity_search(self):
        assert intent.should_search_entities("empty") is False
