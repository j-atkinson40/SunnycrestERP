"""Add funeral home tables — cases, contacts, services, price list, vault orders,
obituaries, invoices, payments, documents, activity log, portal sessions,
and manufacturer relationships.

Revision ID: v4w5x6y7z8a9
Revises: u3v4w5x6y7z8
Create Date: 2026-03-17

"""

from alembic import op
import sqlalchemy as sa

revision = "v4w5x6y7z8a9"
down_revision = "u3v4w5x6y7z8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------ #
    #  1. fh_case_contacts  (created BEFORE fh_cases because of FK)      #
    # ------------------------------------------------------------------ #
    op.create_table(
        "fh_case_contacts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("case_id", sa.String(36), nullable=False),  # FK added after fh_cases
        sa.Column("contact_type", sa.String(30), nullable=False),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column("relationship_to_deceased", sa.String(100), nullable=True),
        sa.Column("phone_primary", sa.String(20), nullable=True),
        sa.Column("phone_secondary", sa.String(20), nullable=True),
        sa.Column("email", sa.String(200), nullable=True),
        sa.Column("address", sa.String(300), nullable=True),
        sa.Column("city", sa.String(100), nullable=True),
        sa.Column("state", sa.String(2), nullable=True),
        sa.Column("zip", sa.String(10), nullable=True),
        sa.Column("is_primary", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("receives_portal_access", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("portal_invite_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("portal_last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ------------------------------------------------------------------ #
    #  2. fh_cases                                                        #
    # ------------------------------------------------------------------ #
    op.create_table(
        "fh_cases",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("case_number", sa.String(30), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="first_call"),
        # Deceased
        sa.Column("deceased_first_name", sa.String(100), nullable=False),
        sa.Column("deceased_middle_name", sa.String(100), nullable=True),
        sa.Column("deceased_last_name", sa.String(100), nullable=False),
        sa.Column("deceased_date_of_birth", sa.Date(), nullable=True),
        sa.Column("deceased_date_of_death", sa.Date(), nullable=False),
        sa.Column("deceased_place_of_death", sa.String(30), nullable=True),
        sa.Column("deceased_place_of_death_name", sa.String(200), nullable=True),
        sa.Column("deceased_place_of_death_city", sa.String(100), nullable=True),
        sa.Column("deceased_place_of_death_state", sa.String(2), nullable=True),
        sa.Column("deceased_gender", sa.String(20), nullable=True),
        sa.Column("deceased_age_at_death", sa.Integer(), nullable=True),
        sa.Column("deceased_ssn_last_four", sa.String(4), nullable=True),
        sa.Column("deceased_veteran", sa.Boolean(), server_default=sa.text("false")),
        # Disposition
        sa.Column("disposition_type", sa.String(30), nullable=True),
        sa.Column("disposition_date", sa.Date(), nullable=True),
        sa.Column("disposition_location", sa.String(200), nullable=True),
        sa.Column("disposition_city", sa.String(100), nullable=True),
        sa.Column("disposition_state", sa.String(2), nullable=True),
        # Service
        sa.Column("service_type", sa.String(40), nullable=True),
        sa.Column("service_date", sa.Date(), nullable=True),
        sa.Column("service_time", sa.String(10), nullable=True),
        sa.Column("service_location", sa.String(200), nullable=True),
        # Visitation
        sa.Column("visitation_date", sa.Date(), nullable=True),
        sa.Column("visitation_start_time", sa.String(10), nullable=True),
        sa.Column("visitation_end_time", sa.String(10), nullable=True),
        sa.Column("visitation_location", sa.String(200), nullable=True),
        # References
        sa.Column("primary_contact_id", sa.String(36), sa.ForeignKey("fh_case_contacts.id"), nullable=True),
        sa.Column("assigned_director_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        # Other
        sa.Column("referred_by", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        # Timestamps
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        # Composite unique
        sa.UniqueConstraint("company_id", "case_number", name="uq_fh_case_number_per_company"),
    )

    # Now add the FK from fh_case_contacts.case_id -> fh_cases.id
    op.create_foreign_key(
        "fk_fh_case_contacts_case_id",
        "fh_case_contacts",
        "fh_cases",
        ["case_id"],
        ["id"],
    )
    op.create_index("ix_fh_case_contacts_case_id", "fh_case_contacts", ["case_id"])

    # ------------------------------------------------------------------ #
    #  3. fh_services                                                     #
    # ------------------------------------------------------------------ #
    op.create_table(
        "fh_services",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("case_id", sa.String(36), sa.ForeignKey("fh_cases.id"), nullable=False, index=True),
        sa.Column("service_category", sa.String(30), nullable=False),
        sa.Column("service_code", sa.String(50), nullable=True),
        sa.Column("service_name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("quantity", sa.Numeric(10, 2), nullable=False, server_default="1"),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("extended_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("is_required", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("is_selected", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("is_package_item", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("package_id", sa.String(36), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ------------------------------------------------------------------ #
    #  4. fh_price_list                                                   #
    # ------------------------------------------------------------------ #
    op.create_table(
        "fh_price_list",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("item_code", sa.String(50), nullable=False),
        sa.Column("category", sa.String(30), nullable=False),
        sa.Column("item_name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("price_type", sa.String(20), nullable=False, server_default="flat"),
        sa.Column("is_ftc_required_disclosure", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("ftc_disclosure_text", sa.Text(), nullable=True),
        sa.Column("is_required_by_law", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ------------------------------------------------------------------ #
    #  5. fh_price_list_versions                                          #
    # ------------------------------------------------------------------ #
    op.create_table(
        "fh_price_list_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("pdf_url", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ------------------------------------------------------------------ #
    #  6. fh_vault_orders                                                 #
    # ------------------------------------------------------------------ #
    op.create_table(
        "fh_vault_orders",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("case_id", sa.String(36), sa.ForeignKey("fh_cases.id"), nullable=False, index=True),
        sa.Column("manufacturer_tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=True),
        sa.Column("order_number", sa.String(50), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="draft"),
        sa.Column("vault_product_id", sa.String(36), nullable=True),
        sa.Column("vault_product_name", sa.String(200), nullable=True),
        sa.Column("vault_product_sku", sa.String(50), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("requested_delivery_date", sa.Date(), nullable=True),
        sa.Column("confirmed_delivery_date", sa.Date(), nullable=True),
        sa.Column("delivery_address", sa.Text(), nullable=True),
        sa.Column("delivery_contact_name", sa.String(200), nullable=True),
        sa.Column("delivery_contact_phone", sa.String(20), nullable=True),
        sa.Column("special_instructions", sa.Text(), nullable=True),
        sa.Column("manufacturer_order_id", sa.String(36), nullable=True),
        sa.Column("delivery_status_last_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ------------------------------------------------------------------ #
    #  7. fh_obituaries                                                   #
    # ------------------------------------------------------------------ #
    op.create_table(
        "fh_obituaries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("case_id", sa.String(36), sa.ForeignKey("fh_cases.id"), nullable=False, index=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="draft"),
        sa.Column("generated_by", sa.String(30), nullable=True),
        sa.Column("ai_prompt_used", sa.Text(), nullable=True),
        sa.Column("family_approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("family_approved_by_contact_id", sa.String(36), sa.ForeignKey("fh_case_contacts.id"), nullable=True),
        sa.Column("family_approval_notes", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("published_locations", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ------------------------------------------------------------------ #
    #  8. fh_invoices                                                     #
    # ------------------------------------------------------------------ #
    op.create_table(
        "fh_invoices",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("case_id", sa.String(36), sa.ForeignKey("fh_cases.id"), nullable=False, index=True),
        sa.Column("invoice_number", sa.String(30), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("subtotal", sa.Numeric(12, 2), nullable=False),
        sa.Column("tax_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("total_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("amount_paid", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("balance_due", sa.Numeric(12, 2), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_to_email", sa.String(200), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ------------------------------------------------------------------ #
    #  9. fh_payments                                                     #
    # ------------------------------------------------------------------ #
    op.create_table(
        "fh_payments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("case_id", sa.String(36), sa.ForeignKey("fh_cases.id"), nullable=False, index=True),
        sa.Column("invoice_id", sa.String(36), sa.ForeignKey("fh_invoices.id"), nullable=False),
        sa.Column("payment_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("payment_method", sa.String(30), nullable=False),
        sa.Column("reference_number", sa.String(100), nullable=True),
        sa.Column("received_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ------------------------------------------------------------------ #
    #  10. fh_documents                                                   #
    # ------------------------------------------------------------------ #
    op.create_table(
        "fh_documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("case_id", sa.String(36), sa.ForeignKey("fh_cases.id"), nullable=False, index=True),
        sa.Column("document_type", sa.String(40), nullable=False),
        sa.Column("document_name", sa.String(200), nullable=False),
        sa.Column("file_url", sa.String(500), nullable=False),
        sa.Column("uploaded_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ------------------------------------------------------------------ #
    #  11. fh_case_activity                                               #
    # ------------------------------------------------------------------ #
    op.create_table(
        "fh_case_activity",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("case_id", sa.String(36), sa.ForeignKey("fh_cases.id"), nullable=False),
        sa.Column("activity_type", sa.String(50), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("performed_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ------------------------------------------------------------------ #
    #  12. fh_portal_sessions                                             #
    # ------------------------------------------------------------------ #
    op.create_table(
        "fh_portal_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("case_id", sa.String(36), sa.ForeignKey("fh_cases.id"), nullable=False),
        sa.Column("contact_id", sa.String(36), sa.ForeignKey("fh_case_contacts.id"), nullable=False),
        sa.Column("access_token", sa.String(100), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_accessed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ------------------------------------------------------------------ #
    #  13. fh_manufacturer_relationships                                  #
    # ------------------------------------------------------------------ #
    op.create_table(
        "fh_manufacturer_relationships",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("funeral_home_tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("manufacturer_tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("account_number", sa.String(50), nullable=True),
        sa.Column("default_delivery_instructions", sa.Text(), nullable=True),
        sa.Column("is_primary", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("negotiated_price_tier", sa.String(50), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ------------------------------------------------------------------ #
    #  Indexes                                                            #
    # ------------------------------------------------------------------ #
    op.create_index("ix_fh_cases_company_status", "fh_cases", ["company_id", "status"])
    op.create_index("ix_fh_cases_company_case_number", "fh_cases", ["company_id", "case_number"])
    op.create_index("ix_fh_vault_orders_manufacturer", "fh_vault_orders", ["manufacturer_tenant_id"])
    op.create_index("ix_fh_case_activity_case_id", "fh_case_activity", ["case_id"])
    op.create_index("ix_fh_portal_sessions_access_token", "fh_portal_sessions", ["access_token"])
    op.create_index("ix_fh_manufacturer_rel_fh", "fh_manufacturer_relationships", ["funeral_home_tenant_id"])
    op.create_index("ix_fh_manufacturer_rel_mfr", "fh_manufacturer_relationships", ["manufacturer_tenant_id"])


def downgrade() -> None:
    op.drop_table("fh_portal_sessions")
    op.drop_table("fh_case_activity")
    op.drop_table("fh_documents")
    op.drop_table("fh_payments")
    op.drop_table("fh_invoices")
    op.drop_table("fh_obituaries")
    op.drop_table("fh_vault_orders")
    op.drop_table("fh_price_list_versions")
    op.drop_table("fh_price_list")
    op.drop_table("fh_services")
    op.drop_table("fh_manufacturer_relationships")
    # Drop FK before dropping fh_cases
    op.drop_constraint("fk_fh_case_contacts_case_id", "fh_case_contacts", type_="foreignkey")
    op.drop_index("ix_fh_case_contacts_case_id", "fh_case_contacts")
    op.drop_table("fh_cases")
    op.drop_table("fh_case_contacts")


# ------------------------------------------------------------------ #
#  FTC seed helper — call from service layer when provisioning a      #
#  funeral home tenant, NOT at migration time.                        #
# ------------------------------------------------------------------ #
def seed_ftc_price_list_items(session, company_id: str) -> None:
    """Insert FTC-required General Price List disclosure items for a new tenant.

    These are the minimum items the FTC Funeral Rule requires funeral homes to
    disclose on their General Price List.  Prices default to $0.00 — the funeral
    home must fill in their actual prices before publishing.
    """
    import uuid as _uuid

    from app.models.fh_price_list import FHPriceListItem

    ftc_items = [
        {
            "item_code": "FTC-BFS",
            "category": "professional_services",
            "item_name": "Basic Services of Funeral Director and Staff",
            "description": "Includes arrangement conference, coordination with cemetery/crematory, preparation and filing of necessary documents, and overhead.",
            "ftc_disclosure_text": "This fee for our basic services will be added to the total cost of the funeral arrangements you select. (This fee is already included in our charges for direct cremations, immediate burials, and forwarding or receiving remains.)",
            "sort_order": 10,
        },
        {
            "item_code": "FTC-EMBALM",
            "category": "professional_services",
            "item_name": "Embalming",
            "description": "Except in certain special cases, embalming is not required by law.",
            "ftc_disclosure_text": "Except in certain special cases, embalming is not required by law. Embalming may be necessary, however, if you select certain funeral arrangements, such as a funeral with viewing. If you do not want embalming, you usually have the right to choose an arrangement that does not require you to pay for it, such as direct cremation or immediate burial.",
            "sort_order": 20,
        },
        {
            "item_code": "FTC-PREP",
            "category": "professional_services",
            "item_name": "Other Preparation of the Body",
            "description": "Cosmetology, dressing, casketing, and other preparation.",
            "ftc_disclosure_text": None,
            "sort_order": 30,
        },
        {
            "item_code": "FTC-VIEW",
            "category": "professional_services",
            "item_name": "Use of Facilities and Staff for Viewing",
            "description": "Includes setup of viewing room, supervision during viewing.",
            "ftc_disclosure_text": None,
            "sort_order": 40,
        },
        {
            "item_code": "FTC-CEREMONY",
            "category": "professional_services",
            "item_name": "Use of Facilities and Staff for Funeral Ceremony",
            "description": "Includes setup of ceremony room, supervision during service.",
            "ftc_disclosure_text": None,
            "sort_order": 50,
        },
        {
            "item_code": "FTC-MEMORIAL",
            "category": "professional_services",
            "item_name": "Use of Facilities and Staff for Memorial Service",
            "description": "Includes setup and supervision for a memorial service without the body present.",
            "ftc_disclosure_text": None,
            "sort_order": 60,
        },
        {
            "item_code": "FTC-GRAVESIDE",
            "category": "professional_services",
            "item_name": "Use of Equipment and Staff for Graveside Service",
            "description": "Includes setup of graveside equipment and supervision.",
            "ftc_disclosure_text": None,
            "sort_order": 70,
        },
        {
            "item_code": "FTC-HEARSE",
            "category": "professional_services",
            "item_name": "Hearse",
            "description": "Transfer of remains to place of service or cemetery.",
            "ftc_disclosure_text": None,
            "sort_order": 80,
        },
        {
            "item_code": "FTC-LIMO",
            "category": "professional_services",
            "item_name": "Limousine",
            "description": "Transportation for family.",
            "ftc_disclosure_text": None,
            "sort_order": 90,
        },
        {
            "item_code": "FTC-TRANSFER",
            "category": "professional_services",
            "item_name": "Transfer of Remains to Funeral Home",
            "description": "Removal and transport of remains from place of death to funeral home.",
            "ftc_disclosure_text": None,
            "sort_order": 100,
        },
        {
            "item_code": "FTC-FWD",
            "category": "professional_services",
            "item_name": "Forwarding Remains to Another Funeral Home",
            "description": "This charge includes removal of remains, basic services of staff, embalming or refrigeration, and local transportation.",
            "ftc_disclosure_text": None,
            "sort_order": 110,
        },
        {
            "item_code": "FTC-RCV",
            "category": "professional_services",
            "item_name": "Receiving Remains from Another Funeral Home",
            "description": "This charge includes basic services of staff, transportation of remains to funeral home, and transportation to cemetery or crematory.",
            "ftc_disclosure_text": None,
            "sort_order": 120,
        },
        {
            "item_code": "FTC-DC",
            "category": "professional_services",
            "item_name": "Direct Cremation",
            "description": "Our charge for direct cremation (without ceremony) includes removal of remains, basic services of staff, refrigeration, transport to crematory, and return of cremated remains.",
            "ftc_disclosure_text": "If you want to arrange a direct cremation, you can use an alternative container. Alternative containers encase the body and can be made of materials like fiberboard or composition materials (with or without an outside covering). The containers we provide are [listed on GPL].",
            "sort_order": 130,
        },
        {
            "item_code": "FTC-IB",
            "category": "professional_services",
            "item_name": "Immediate Burial",
            "description": "Our charge for immediate burial (without ceremony) includes removal of remains, basic services of staff, and local transportation to cemetery.",
            "ftc_disclosure_text": None,
            "sort_order": 140,
        },
        {
            "item_code": "FTC-CASKET",
            "category": "merchandise",
            "item_name": "Caskets",
            "description": "A complete price list will be provided at the funeral home.",
            "ftc_disclosure_text": "A complete price list will be provided at the funeral home.",
            "sort_order": 200,
        },
        {
            "item_code": "FTC-VAULT",
            "category": "merchandise",
            "item_name": "Outer Burial Containers",
            "description": "A complete price list will be provided at the funeral home.",
            "ftc_disclosure_text": "In most areas of the country, state or local law does not require that you buy a container to surround the casket in the grave. However, many cemeteries require that you have such a container so that the grave will not sink in. Either a grave liner or a burial vault will satisfy these requirements.",
            "sort_order": 210,
        },
        {
            "item_code": "FTC-ALT",
            "category": "merchandise",
            "item_name": "Alternative Containers",
            "description": "Containers for direct cremation that are not traditional caskets.",
            "ftc_disclosure_text": None,
            "sort_order": 220,
        },
    ]

    for item_data in ftc_items:
        item = FHPriceListItem(
            id=str(_uuid.uuid4()),
            company_id=company_id,
            item_code=item_data["item_code"],
            category=item_data["category"],
            item_name=item_data["item_name"],
            description=item_data["description"],
            unit_price=0,
            price_type="flat",
            is_ftc_required_disclosure=True,
            ftc_disclosure_text=item_data["ftc_disclosure_text"],
            is_required_by_law=False,
            is_active=True,
            sort_order=item_data["sort_order"],
        )
        session.add(item)

    session.flush()
