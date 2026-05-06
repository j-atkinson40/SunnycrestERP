"""Phase D-10 tests — block composer correctness.

Each block kind's compile_to_jinja produces expected Jinja fragments;
the composer concatenates fragments correctly; the composed Jinja
renders against test contexts without errors.
"""

from __future__ import annotations

import pytest

from app.services.documents import block_registry as br


# ─── Per-kind compile_to_jinja output ───────────────────────────


class TestHeaderCompile:
    def test_emits_header_with_title(self):
        kind = br.get_block_kind("header")
        out = kind.compile_to_jinja(
            {
                "title": "{{ document_title }}",
                "subtitle": "Test subtitle",
                "show_logo": True,
                "show_date": True,
                "accent_color": "#9C5640",
            },
            "",
        )
        assert "<header" in out
        assert "{{ document_title }}" in out
        assert "Test subtitle" in out
        assert "company_logo_url" in out
        assert "{{ document_date }}" in out

    def test_omits_logo_when_disabled(self):
        kind = br.get_block_kind("header")
        out = kind.compile_to_jinja(
            {"show_logo": False, "title": "X", "show_date": False},
            "",
        )
        assert "<img" not in out
        assert "{{ document_date }}" not in out


class TestBodySectionCompile:
    def test_emits_section_with_heading_and_body(self):
        kind = br.get_block_kind("body_section")
        out = kind.compile_to_jinja(
            {"heading": "Bill To", "body": "{{ customer_name }}"},
            "",
        )
        assert "<section" in out
        assert "Bill To" in out
        assert "{{ customer_name }}" in out


class TestLineItemsCompile:
    def test_emits_table_iterating_over_items(self):
        kind = br.get_block_kind("line_items")
        out = kind.compile_to_jinja(
            {
                "items_variable": "items",
                "columns": [
                    {"header": "Description", "field": "description"},
                    {"header": "Qty", "field": "quantity"},
                ],
            },
            "",
        )
        assert "<table" in out
        assert "{% for item in items %}" in out
        assert "{% endfor %}" in out
        assert "{{ item.description }}" in out
        assert "{{ item.quantity }}" in out
        assert "<th>Description</th>" in out

    def test_uses_default_columns_when_omitted(self):
        kind = br.get_block_kind("line_items")
        out = kind.compile_to_jinja({"items_variable": "items"}, "")
        # Default columns include description, quantity, unit_price, total
        assert "{{ item.description }}" in out
        assert "{{ item.quantity }}" in out


class TestTotalsCompile:
    def test_emits_totals_table_with_emphasis(self):
        kind = br.get_block_kind("totals")
        out = kind.compile_to_jinja(
            {
                "rows": [
                    {"label": "Subtotal", "variable": "subtotal"},
                    {"label": "Total", "variable": "total", "emphasis": True},
                ]
            },
            "",
        )
        assert "Subtotal" in out
        assert "{{ subtotal }}" in out
        assert "doc-total-emphasis" in out
        assert "{{ total }}" in out


class TestSignatureCompile:
    def test_emits_signature_blocks_with_anchors(self):
        kind = br.get_block_kind("signature")
        out = kind.compile_to_jinja(
            {
                "parties": [{"role": "Customer"}, {"role": "Sales Rep"}],
                "show_dates": True,
            },
            "",
        )
        assert "Customer" in out
        assert "Sales Rep" in out
        assert "/sig_party_1/" in out
        assert "/sig_party_2/" in out
        assert "Date:" in out


class TestConditionalWrapperCompile:
    def test_wraps_children_jinja_in_if_block(self):
        kind = br.get_block_kind("conditional_wrapper")
        out = kind.compile_to_jinja(
            {"__condition__": "is_cremation == True"},
            "<p>cremation content</p>",
        )
        assert "{% if is_cremation == True %}" in out
        assert "<p>cremation content</p>" in out
        assert "{% endif %}" in out

    def test_empty_children_emits_nothing(self):
        kind = br.get_block_kind("conditional_wrapper")
        out = kind.compile_to_jinja(
            {"__condition__": "True"},
            "",
        )
        assert out == ""


# ─── Variable schema aggregation ────────────────────────────────


class TestVariableSchema:
    def test_header_declares_company_and_document_vars(self):
        kind = br.get_block_kind("header")
        vars_ = kind.declared_variables(
            {"show_logo": True, "show_date": True}
        )
        assert "company_name" in vars_
        assert "document_title" in vars_
        assert "company_logo_url" in vars_
        assert "document_date" in vars_

    def test_line_items_declares_iteration_variable(self):
        kind = br.get_block_kind("line_items")
        vars_ = kind.declared_variables({"items_variable": "transactions"})
        assert "transactions" in vars_

    def test_totals_declares_each_row_variable(self):
        kind = br.get_block_kind("totals")
        vars_ = kind.declared_variables(
            {
                "rows": [
                    {"label": "Subtotal", "variable": "subtotal"},
                    {"label": "Tax", "variable": "tax"},
                    {"label": "Total", "variable": "total"},
                ]
            }
        )
        assert "subtotal" in vars_
        assert "tax" in vars_
        assert "total" in vars_


# ─── Composer end-to-end ────────────────────────────────────────


class TestComposerEndToEnd:
    """Compose a tree of blocks, render result through Jinja, verify."""

    def test_composer_handles_empty_block_set(self, db, template_version):
        from app.services.documents.block_composer import (
            compose_blocks_to_jinja,
        )

        result = compose_blocks_to_jinja(db, template_version.id)
        assert "<!DOCTYPE html>" in result.body_template
        assert "Empty document" in result.body_template
        assert result.block_count == 0

    def test_composer_aggregates_declared_vars(
        self, db, template_version
    ):
        from app.services.documents.block_composer import (
            compose_blocks_to_jinja,
        )
        from app.services.documents.block_service import add_block

        add_block(
            db,
            version_id=template_version.id,
            block_kind="header",
            config={"show_logo": True, "show_date": True, "title": "X"},
        )
        add_block(
            db,
            version_id=template_version.id,
            block_kind="line_items",
            config={"items_variable": "items"},
        )
        result = compose_blocks_to_jinja(db, template_version.id)
        # Aggregated and deduped
        assert "company_name" in result.declared_variables
        assert "items" in result.declared_variables
        # Sorted
        assert result.declared_variables == sorted(set(result.declared_variables))

    def test_composer_renders_through_jinja(self, db, template_version):
        """End-to-end: compose blocks, render the result via Jinja with
        sample data, verify substantive content appears."""
        from jinja2 import Environment

        from app.services.documents.block_composer import (
            compose_blocks_to_jinja,
        )
        from app.services.documents.block_service import add_block

        add_block(
            db,
            version_id=template_version.id,
            block_kind="header",
            config={
                "title": "Invoice {{ invoice_number }}",
                "show_logo": False,
                "show_date": True,
            },
        )
        add_block(
            db,
            version_id=template_version.id,
            block_kind="line_items",
            config={"items_variable": "items"},
        )
        result = compose_blocks_to_jinja(db, template_version.id)

        env = Environment()
        tpl = env.from_string(result.body_template)
        rendered = tpl.render(
            invoice_number="INV-001",
            company_name="Acme Co",
            document_title="Test",
            document_date="2026-06-01",
            items=[
                {
                    "description": "Widget",
                    "quantity": 2,
                    "unit_price": 10.0,
                    "line_total": 20.0,
                }
            ],
        )
        assert "INV-001" in rendered
        assert "Widget" in rendered
        assert "2026-06-01" in rendered

    def test_composer_handles_nested_conditional(
        self, db, template_version
    ):
        from jinja2 import Environment

        from app.services.documents.block_composer import (
            compose_blocks_to_jinja,
        )
        from app.services.documents.block_service import add_block

        wrapper = add_block(
            db,
            version_id=template_version.id,
            block_kind="conditional_wrapper",
            config={},
            condition="show_section",
        )
        add_block(
            db,
            version_id=template_version.id,
            block_kind="body_section",
            config={"heading": "Conditional", "body": "Visible content"},
            parent_block_id=wrapper.id,
        )
        result = compose_blocks_to_jinja(db, template_version.id)

        env = Environment()
        tpl = env.from_string(result.body_template)

        rendered_visible = tpl.render(
            show_section=True, company_name="Acme", document_title="Test",
        )
        assert "Visible content" in rendered_visible

        rendered_hidden = tpl.render(
            show_section=False, company_name="Acme", document_title="Test",
        )
        assert "Visible content" not in rendered_hidden


# ─── Document type catalog ──────────────────────────────────────


class TestDocumentTypeCatalog:
    def test_invoice_type_present_with_starter_blocks(self):
        from app.services.documents.document_types import get_document_type

        invoice = get_document_type("invoice")
        assert invoice is not None
        assert invoice.category == "invoices"
        assert invoice.starter_blocks  # has scaffolding
        block_kinds = {b.block_kind for b in invoice.starter_blocks}
        assert "header" in block_kinds
        assert "line_items" in block_kinds
        assert "totals" in block_kinds

    def test_arrangement_summary_includes_conditional_wrapper(self):
        from app.services.documents.document_types import get_document_type

        arr = get_document_type("arrangement_summary")
        assert arr is not None
        kinds = [b.block_kind for b in arr.starter_blocks]
        assert "conditional_wrapper" in kinds

    def test_categories_in_canonical_order(self):
        from app.services.documents.document_types import list_categories

        cats = list_categories()
        ids = [c[0] for c in cats]
        # Invoices first; Other last per the canonical order in the catalog.
        assert ids[0] == "invoices"
        assert ids[-1] == "other"


# Reuse the engine + db + template_version fixtures from
# test_documents_d10_blocks.py — a separate import path lets us
# share without duplicating.

from tests.test_documents_d10_blocks import (  # noqa: E402
    db,
    engine,
    template_version,
)


# Silence "imported but not used" via a sentinel tuple.
_unused = (db, engine, template_version)
