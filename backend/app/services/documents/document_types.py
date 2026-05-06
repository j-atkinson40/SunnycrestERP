"""Curated document type catalog (Phase D-10).

`document_type` is a free-form String(64) on `documents` and
`document_templates`, but the editor needs a curated list to drive
the type-picker UI + provide starter block sequences for new
templates.

Per the Phase 2 architectural decisions: tenants can author templates
of existing types, but only platform admins can introduce new types.
This module is the platform-curated source of truth.

The starter block sequence is what the "create new template" flow
adds when the operator picks a type — a reasonable default scaffold
that the operator then customizes.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class DocumentTypeStarterBlock:
    """One block in a starter sequence.

    `config` is the initial config the block is created with; the
    operator modifies via the editor.
    """

    block_kind: str
    config: dict
    condition: str | None = None
    """For conditional_wrapper starter blocks."""


@dataclass(frozen=True)
class DocumentTypeRegistration:
    type_id: str  # matches `documents.document_type` value
    display_name: str
    category: str  # editor browser category
    description: str
    starter_blocks: list[DocumentTypeStarterBlock] = field(default_factory=list)
    recommended_variables: list[str] = field(default_factory=list)


# ─── Categories ─────────────────────────────────────────────────────


CATEGORIES: list[tuple[str, str]] = [
    ("invoices", "Invoices"),
    ("statements", "Statements"),
    ("price_lists", "Price Lists"),
    ("quotes", "Quotes"),
    ("certificates", "Certificates"),
    ("arrangements", "Arrangements"),
    ("service_documents", "Service Documents"),
    ("production_documents", "Production Documents"),
    ("emails", "Email Templates"),
    ("other", "Other"),
]


# ─── Type registrations ────────────────────────────────────────────


_DOCUMENT_TYPES: dict[str, DocumentTypeRegistration] = {}


def _register(reg: DocumentTypeRegistration) -> None:
    _DOCUMENT_TYPES[reg.type_id] = reg


# Invoices
_register(
    DocumentTypeRegistration(
        type_id="invoice",
        display_name="Invoice",
        category="invoices",
        description=(
            "Customer-facing invoice with line items, totals, and "
            "payment terms."
        ),
        starter_blocks=[
            DocumentTypeStarterBlock(
                block_kind="header",
                config={
                    "title": "Invoice {{ invoice_number }}",
                    "subtitle": "{{ company_name }}",
                    "show_date": True,
                },
            ),
            DocumentTypeStarterBlock(
                block_kind="body_section",
                config={
                    "heading": "Bill To",
                    "body": "{{ customer_name }}<br>{{ customer_address }}",
                },
            ),
            DocumentTypeStarterBlock(
                block_kind="line_items",
                config={"items_variable": "items"},
            ),
            DocumentTypeStarterBlock(
                block_kind="totals",
                config={},
            ),
        ],
        recommended_variables=[
            "invoice_number",
            "customer_name",
            "customer_address",
            "items",
            "subtotal",
            "tax",
            "total",
            "due_date",
        ],
    )
)

# Statements
_register(
    DocumentTypeRegistration(
        type_id="statement",
        display_name="Statement",
        category="statements",
        description=(
            "Monthly or periodic customer statement with itemized "
            "transactions and balance."
        ),
        starter_blocks=[
            DocumentTypeStarterBlock(
                block_kind="header",
                config={
                    "title": "Statement",
                    "subtitle": "{{ statement_period }}",
                },
            ),
            DocumentTypeStarterBlock(
                block_kind="line_items",
                config={"items_variable": "transactions"},
            ),
            DocumentTypeStarterBlock(
                block_kind="totals",
                config={
                    "rows": [
                        {"label": "Previous Balance", "variable": "previous_balance"},
                        {"label": "Charges", "variable": "charges"},
                        {"label": "Payments", "variable": "payments"},
                        {"label": "Current Balance", "variable": "current_balance", "emphasis": True},
                    ]
                },
            ),
        ],
        recommended_variables=[
            "statement_period",
            "transactions",
            "previous_balance",
            "charges",
            "payments",
            "current_balance",
        ],
    )
)

# Price lists
_register(
    DocumentTypeRegistration(
        type_id="price_list",
        display_name="Price List",
        category="price_lists",
        description="Pricing catalog grouped by category.",
        starter_blocks=[
            DocumentTypeStarterBlock(
                block_kind="header",
                config={
                    "title": "Price List",
                    "subtitle": "{{ effective_date }}",
                },
            ),
            DocumentTypeStarterBlock(
                block_kind="line_items",
                config={"items_variable": "products"},
            ),
        ],
        recommended_variables=["effective_date", "products"],
    )
)

# Quotes
_register(
    DocumentTypeRegistration(
        type_id="quote",
        display_name="Quote",
        category="quotes",
        description="Sales quote with proposed line items and pricing.",
        starter_blocks=[
            DocumentTypeStarterBlock(
                block_kind="header",
                config={
                    "title": "Quote {{ quote_number }}",
                    "subtitle": "Valid until {{ valid_until }}",
                },
            ),
            DocumentTypeStarterBlock(
                block_kind="body_section",
                config={
                    "heading": "Prepared For",
                    "body": "{{ customer_name }}<br>{{ customer_address }}",
                },
            ),
            DocumentTypeStarterBlock(
                block_kind="line_items",
                config={"items_variable": "items"},
            ),
            DocumentTypeStarterBlock(
                block_kind="totals",
                config={},
            ),
            DocumentTypeStarterBlock(
                block_kind="signature",
                config={"parties": [{"role": "Customer"}, {"role": "Sales Representative"}]},
            ),
        ],
        recommended_variables=[
            "quote_number",
            "customer_name",
            "valid_until",
            "items",
            "subtotal",
            "tax",
            "total",
        ],
    )
)

# Certificates (signature, compliance, etc.)
_register(
    DocumentTypeRegistration(
        type_id="signature_certificate",
        display_name="Certificate of Completion",
        category="certificates",
        description=(
            "Audit certificate issued at signing-envelope completion. "
            "Generated automatically by the signing service."
        ),
        starter_blocks=[],
        recommended_variables=[
            "envelope_subject",
            "completed_at",
            "parties",
            "events",
        ],
    )
)
_register(
    DocumentTypeRegistration(
        type_id="social_service_certificate",
        display_name="Social Service Certificate",
        category="certificates",
        description=(
            "Government Social Service Graveliner program delivery "
            "confirmation. Auto-generated on delivery."
        ),
        starter_blocks=[
            DocumentTypeStarterBlock(
                block_kind="header",
                config={"title": "Social Service Certificate"},
            ),
            DocumentTypeStarterBlock(
                block_kind="body_section",
                config={
                    "heading": "Delivery Confirmation",
                    "body": (
                        "Deceased: {{ deceased_name }}<br>"
                        "Delivered: {{ delivered_at }}<br>"
                        "Cemetery: {{ cemetery_name }}"
                    ),
                },
            ),
            DocumentTypeStarterBlock(
                block_kind="signature",
                config={"parties": [{"role": "Authorized Representative"}]},
            ),
        ],
        recommended_variables=[
            "deceased_name",
            "delivered_at",
            "cemetery_name",
        ],
    )
)

# Arrangements (FH-vertical)
_register(
    DocumentTypeRegistration(
        type_id="arrangement_summary",
        display_name="Arrangement Summary",
        category="arrangements",
        description=(
            "Funeral home arrangement intake summary covering "
            "deceased, service, disposition, and selected goods."
        ),
        starter_blocks=[
            DocumentTypeStarterBlock(
                block_kind="header",
                config={
                    "title": "Arrangement Summary",
                    "subtitle": "{{ deceased_name }}",
                },
            ),
            DocumentTypeStarterBlock(
                block_kind="body_section",
                config={
                    "heading": "Decedent Information",
                    "body": (
                        "Name: {{ deceased_name }}<br>"
                        "Date of Death: {{ date_of_death }}"
                    ),
                },
            ),
            DocumentTypeStarterBlock(
                block_kind="body_section",
                config={
                    "heading": "Service Details",
                    "body": (
                        "Type: {{ service_type }}<br>"
                        "Date: {{ service_date }}<br>"
                        "Location: {{ service_location }}"
                    ),
                },
            ),
            DocumentTypeStarterBlock(
                block_kind="conditional_wrapper",
                config={"label": "Cremation-only sections"},
                condition="disposition == 'cremation'",
            ),
            DocumentTypeStarterBlock(
                block_kind="signature",
                config={"parties": [{"role": "Informant"}, {"role": "Funeral Director"}]},
            ),
        ],
        recommended_variables=[
            "deceased_name",
            "date_of_death",
            "service_type",
            "service_date",
            "service_location",
            "disposition",
        ],
    )
)
_register(
    DocumentTypeRegistration(
        type_id="urn_engraving_form",
        display_name="Urn Engraving Form",
        category="arrangements",
        description=(
            "Wilbert urn engraving order form. Submitted to Wilbert "
            "with proof approval."
        ),
        starter_blocks=[],
        recommended_variables=[
            "urn_sku",
            "decedent_name",
            "date_of_birth",
            "date_of_death",
        ],
    )
)
_register(
    DocumentTypeRegistration(
        type_id="disinterment_release",
        display_name="Disinterment Release",
        category="arrangements",
        description=(
            "Cemetery disinterment release authorization. Multi-party "
            "signatures required (FH director, cemetery rep, "
            "next-of-kin, manufacturer)."
        ),
        starter_blocks=[],
        recommended_variables=[
            "deceased_name",
            "original_burial_date",
            "destination_cemetery",
        ],
    )
)

# Production documents
_register(
    DocumentTypeRegistration(
        type_id="legacy_vault_print",
        display_name="Legacy Vault Print",
        category="production_documents",
        description="Manufacturing-side vault production print/instructions.",
        starter_blocks=[],
        recommended_variables=["vault_model", "personalization", "delivery_date"],
    )
)
_register(
    DocumentTypeRegistration(
        type_id="safety_program",
        display_name="Safety Program",
        category="production_documents",
        description=(
            "Monthly OSHA safety program. Generated by AI from OSHA "
            "regulatory scrape + tenant context."
        ),
        starter_blocks=[],
        recommended_variables=["topic_title", "month_year", "osha_code"],
    )
)

# Email templates
_register(
    DocumentTypeRegistration(
        type_id="email",
        display_name="Email Template",
        category="emails",
        description=(
            "Generic email template. Body is HTML-rendered; subject "
            "renders separately."
        ),
        starter_blocks=[
            DocumentTypeStarterBlock(
                block_kind="body_section",
                config={
                    "heading": "",
                    "body": "Hello {{ recipient_name }},<br><br>...",
                },
            ),
        ],
        recommended_variables=["recipient_name", "company_name"],
    )
)


# ─── Public API ─────────────────────────────────────────────────────


def list_document_types() -> list[DocumentTypeRegistration]:
    """All curated document types, sorted by category then display_name."""
    return sorted(
        _DOCUMENT_TYPES.values(),
        key=lambda r: (r.category, r.display_name),
    )


def get_document_type(type_id: str) -> DocumentTypeRegistration | None:
    return _DOCUMENT_TYPES.get(type_id)


def list_categories() -> list[tuple[str, str]]:
    """(category_id, display_name) pairs in canonical order."""
    return list(CATEGORIES)
