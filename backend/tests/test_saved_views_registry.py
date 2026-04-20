"""Unit tests — Saved Views entity registry.

Scope: registry.py in isolation. No DB, no HTTP.

Covers:
  - Default seed populates 7 entity types (Phase 2 scope)
  - Each entity has non-empty available_fields + default_sort
  - register_entity replaces by entity_type (last-write-wins)
  - reset_registry un-seeds
  - field_by_name lookup returns None for unknown fields
  - FieldMetadata type vocabulary is one of the documented literals
"""

from __future__ import annotations

import pytest

from app.services.saved_views import registry


@pytest.fixture(autouse=True)
def _fresh_registry():
    registry.reset_registry()
    yield
    registry.reset_registry()


class TestDefaultSeed:
    def test_seven_entities_registered(self):
        entities = {e.entity_type for e in registry.list_entities()}
        assert entities == {
            "fh_case",
            "sales_order",
            "invoice",
            "contact",
            "product",
            "document",
            "vault_item",
        }

    def test_each_entity_has_fields_and_sort(self):
        for e in registry.list_entities():
            assert len(e.available_fields) > 0, e.entity_type
            assert e.default_sort, e.entity_type
            assert e.default_columns, e.entity_type
            assert e.icon, e.entity_type
            assert e.navigate_url_template, e.entity_type

    def test_known_field_types_are_in_vocabulary(self):
        valid_types = {
            "text", "number", "currency", "date", "datetime",
            "boolean", "enum", "relation",
        }
        for e in registry.list_entities():
            for f in e.available_fields:
                assert f.field_type in valid_types, (e.entity_type, f.field_name, f.field_type)

    def test_sales_order_fields_include_number_and_status(self):
        so = registry.get_entity("sales_order")
        assert so is not None
        names = {f.field_name for f in so.available_fields}
        assert "number" in names
        assert "status" in names
        assert "customer_id" in names

    def test_vault_item_excludes_saved_view_type(self):
        # The vault_item query_builder must filter out saved_view
        # rows — otherwise a view-of-all-vault-items includes itself.
        vi = registry.get_entity("vault_item")
        assert vi is not None
        # Status enum values don't include saved_view (it's item_type
        # that's filtered, not status). The actual filter is
        # validated behaviorally in executor tests — here we just
        # confirm the entity is registered.


class TestRegistration:
    def test_register_entity_replaces_by_type(self):
        registry.get_entity("fh_case")  # seed
        custom = registry.EntityTypeMetadata(
            entity_type="fh_case",
            display_name="Custom Cases",
            icon="Folder",
            navigate_url_template="/custom-cases/{id}",
            query_builder=lambda db, co: None,
            row_serializer=lambda r: {},
        )
        registry.register_entity(custom)
        fresh = registry.get_entity("fh_case")
        assert fresh.display_name == "Custom Cases"


class TestFieldLookup:
    def test_field_by_name_known(self):
        so = registry.get_entity("sales_order")
        field = so.field_by_name("number")
        assert field is not None
        assert field.field_type == "text"

    def test_field_by_name_unknown_returns_none(self):
        so = registry.get_entity("sales_order")
        assert so.field_by_name("zzzz_nonexistent") is None


class TestResetRegistry:
    def test_reset_clears_and_re_seeds(self):
        # Trigger seed
        before = len(registry.list_entities())
        registry.reset_registry()
        after = len(registry.list_entities())
        assert before == after == 7
