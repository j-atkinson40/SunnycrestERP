"""Funeral Home Vertical Phase FH-1a — Case model + satellites + vault + casket_products.

Creates the foundation for the funeral home vertical. 14 case-related tables,
4 vault tables, casket_products, and case_field_config. All cross-tenant FKs
are nullable (manual entry fallback when no network connection). Multi-location
via funeral_cases.location_id (nullable) following the same pattern as
sales_orders.location_id.

SSN storage: case_deceased.ssn_encrypted holds Fernet-encrypted bytes.
The application layer is responsible for encryption/decryption.
Never logged or serialized without explicit request.
"""

import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "fh_01_case_model"
down_revision = "vault_06_legacy_prints"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ======================================================================
    # 1. funeral_cases — the root case record
    # ======================================================================
    op.create_table(
        "funeral_cases",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("location_id", sa.String(36), sa.ForeignKey("locations.id"), nullable=True),
        sa.Column("case_number", sa.String(50), nullable=False),  # FC-2026-0001
        sa.Column("status", sa.String(50), nullable=False, server_default="active"),
        # active | on_hold | completed | cancelled
        sa.Column("director_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("current_step", sa.String(100), nullable=False, server_default="arrangement_conference"),
        sa.Column("completed_steps", JSONB, nullable=True),   # list of step keys
        sa.Column("opened_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        # Story Thread (Phase 1 stores narrative; Phase 1b fires cross-tenant orders)
        sa.Column("story_thread_status", sa.String(50), nullable=True, server_default="building"),
        # building | ready | approved
        sa.Column("story_thread_narrative", sa.Text, nullable=True),
        sa.Column("story_thread_compiled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("all_selections_approved_at", sa.DateTime(timezone=True), nullable=True),
        # Scribe recording
        sa.Column("transcript_r2_key", sa.String(500), nullable=True),
        # Cross-tenant FKs — nullable; populated when connection exists
        sa.Column("vault_manufacturer_company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=True),
        sa.Column("cemetery_company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=True),
        sa.Column("crematory_company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=True),
        sa.Column("casket_manufacturer_company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_funeral_cases_company", "funeral_cases", ["company_id"])
    op.create_index("ix_funeral_cases_company_status", "funeral_cases", ["company_id", "status"])
    op.create_index("ix_funeral_cases_location", "funeral_cases", ["location_id"])
    op.create_index("ix_funeral_cases_director", "funeral_cases", ["director_id"])
    op.create_index("uq_funeral_cases_company_number", "funeral_cases", ["company_id", "case_number"], unique=True)

    # ======================================================================
    # 2. case_deceased — identity, vital stats, DC fields
    # ======================================================================
    op.create_table(
        "case_deceased",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("case_id", sa.String(36), sa.ForeignKey("funeral_cases.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        # Name
        sa.Column("first_name", sa.String(100), nullable=True),
        sa.Column("middle_name", sa.String(100), nullable=True),
        sa.Column("last_name", sa.String(100), nullable=True),
        sa.Column("suffix", sa.String(20), nullable=True),
        sa.Column("maiden_name", sa.String(100), nullable=True),
        sa.Column("aka", sa.String(255), nullable=True),
        # Demographics
        sa.Column("date_of_birth", sa.Date, nullable=True),
        sa.Column("birthplace_city", sa.String(100), nullable=True),
        sa.Column("birthplace_state", sa.String(50), nullable=True),
        sa.Column("birthplace_country", sa.String(100), nullable=True),
        sa.Column("sex", sa.String(20), nullable=True),
        sa.Column("race", JSONB, nullable=True),              # multi-select
        sa.Column("ethnicity", sa.String(100), nullable=True),
        sa.Column("marital_status", sa.String(50), nullable=True),
        sa.Column("religion", sa.String(100), nullable=True),
        # SSN — encrypted at rest (Fernet). Never log. Never return in API by default.
        sa.Column("ssn_encrypted", sa.LargeBinary, nullable=True),
        sa.Column("ssn_last_four", sa.String(4), nullable=True),   # unencrypted for UI mask display
        # Death
        sa.Column("date_of_death", sa.Date, nullable=True),
        sa.Column("time_of_death", sa.Time, nullable=True),
        sa.Column("place_of_death_name", sa.String(255), nullable=True),
        sa.Column("place_of_death_city", sa.String(100), nullable=True),
        sa.Column("place_of_death_state", sa.String(50), nullable=True),
        sa.Column("place_of_death_zip", sa.String(20), nullable=True),
        sa.Column("cause_of_death", sa.Text, nullable=True),
        sa.Column("manner_of_death", sa.String(50), nullable=True),
        # natural | accident | suicide | homicide | pending | undetermined
        # Residence (last known)
        sa.Column("residence_address", sa.String(255), nullable=True),
        sa.Column("residence_city", sa.String(100), nullable=True),
        sa.Column("residence_state", sa.String(50), nullable=True),
        sa.Column("residence_zip", sa.String(20), nullable=True),
        sa.Column("residence_county", sa.String(100), nullable=True),
        sa.Column("residence_country", sa.String(100), nullable=True),
        # Occupation / education
        sa.Column("occupation", sa.String(255), nullable=True),
        sa.Column("industry", sa.String(255), nullable=True),
        sa.Column("years_worked", sa.Integer, nullable=True),
        sa.Column("education_level", sa.String(100), nullable=True),
        # Parents (for DC)
        sa.Column("father_name", sa.String(255), nullable=True),
        sa.Column("father_birthplace", sa.String(255), nullable=True),
        sa.Column("mother_maiden_name", sa.String(255), nullable=True),
        sa.Column("mother_birthplace", sa.String(255), nullable=True),
        # Spouse
        sa.Column("spouse_name", sa.String(255), nullable=True),
        sa.Column("spouse_still_living", sa.Boolean, nullable=True),
        # Extracted confidence (from Scribe) — per-field metadata
        sa.Column("field_confidence", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_case_deceased_company", "case_deceased", ["company_id"])

    # ======================================================================
    # 3. case_informants — NOK, authorizing agents
    # ======================================================================
    op.create_table(
        "case_informants",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("case_id", sa.String(36), sa.ForeignKey("funeral_cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("relationship", sa.String(100), nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("address", sa.String(500), nullable=True),
        sa.Column("is_primary", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_authorizing", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("authorization_signed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("authorization_method", sa.String(50), nullable=True),
        # in_person | emailed | faxed | digital
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_case_informants_case", "case_informants", ["case_id"])

    # ======================================================================
    # 4. case_service — service planning
    # ======================================================================
    op.create_table(
        "case_service",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("case_id", sa.String(36), sa.ForeignKey("funeral_cases.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("service_type", sa.String(100), nullable=True),
        # graveside | chapel | church | memorial | celebration_of_life | no_service
        sa.Column("service_date", sa.Date, nullable=True),
        sa.Column("service_time", sa.Time, nullable=True),
        sa.Column("service_location_name", sa.String(255), nullable=True),
        sa.Column("service_location_address", sa.String(500), nullable=True),
        sa.Column("officiant_name", sa.String(255), nullable=True),
        sa.Column("officiant_phone", sa.String(50), nullable=True),
        # Visitation
        sa.Column("visitation_date", sa.Date, nullable=True),
        sa.Column("visitation_start_time", sa.Time, nullable=True),
        sa.Column("visitation_end_time", sa.Time, nullable=True),
        sa.Column("visitation_location", sa.String(255), nullable=True),
        # People
        sa.Column("pallbearers", JSONB, nullable=True),   # list[str]
        sa.Column("honorary_pallbearers", JSONB, nullable=True),
        sa.Column("music_selections", JSONB, nullable=True),
        sa.Column("readings", JSONB, nullable=True),
        sa.Column("special_instructions", sa.Text, nullable=True),
        # Obituary
        sa.Column("obituary_draft", sa.Text, nullable=True),
        sa.Column("obituary_final", sa.Text, nullable=True),
        sa.Column("obituary_published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("obituary_newspapers", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ======================================================================
    # 5. case_disposition — burial / cremation / entombment / other
    # ======================================================================
    op.create_table(
        "case_disposition",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("case_id", sa.String(36), sa.ForeignKey("funeral_cases.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("disposition_type", sa.String(50), nullable=True),
        # burial | cremation | entombment | donation | other
        # Death certificate
        sa.Column("death_certificate_status", sa.String(50), nullable=True, server_default="not_filed"),
        # not_filed | pending | filed | received
        sa.Column("death_certificate_filed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("death_certificate_number", sa.String(100), nullable=True),
        sa.Column("death_certificate_certified_copies_count", sa.Integer, nullable=True, server_default="0"),
        # Burial permit
        sa.Column("burial_permit_number", sa.String(100), nullable=True),
        sa.Column("burial_permit_issued_at", sa.DateTime(timezone=True), nullable=True),
        # Notes on disposition
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ======================================================================
    # 6. case_cemetery — cemetery details (burial only)
    # ======================================================================
    op.create_table(
        "case_cemetery",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("case_id", sa.String(36), sa.ForeignKey("funeral_cases.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        # Manual entry fields (fallback when no network connection)
        sa.Column("cemetery_name", sa.String(255), nullable=True),
        sa.Column("cemetery_address", sa.String(500), nullable=True),
        sa.Column("section", sa.String(50), nullable=True),
        sa.Column("row", sa.String(50), nullable=True),
        sa.Column("plot_number", sa.String(50), nullable=True),
        # Cross-tenant plot reference (FH-1b)
        sa.Column("plot_id", sa.String(36), nullable=True),   # cemetery_plots.id when connected
        sa.Column("plot_reserved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("plot_payment_status", sa.String(50), nullable=True, server_default="unpaid"),
        # unpaid | paid | refunded
        sa.Column("plot_payment_transaction_id", sa.String(255), nullable=True),
        sa.Column("opening_closing_scheduled_for", sa.DateTime(timezone=True), nullable=True),
        sa.Column("grave_marker_notes", sa.Text, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ======================================================================
    # 7. case_cremation — cremation specifics
    # ======================================================================
    op.create_table(
        "case_cremation",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("case_id", sa.String(36), sa.ForeignKey("funeral_cases.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("crematory_name", sa.String(255), nullable=True),
        sa.Column("crematory_address", sa.String(500), nullable=True),
        sa.Column("authorization_signed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cremation_scheduled_for", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cremation_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cremation_number", sa.String(100), nullable=True),
        sa.Column("urn_selected", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("urn_product_id", sa.String(36), nullable=True),
        sa.Column("disposition_of_ashes", sa.String(255), nullable=True),
        # returned_to_family | scattered | interred | split
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ======================================================================
    # 8. case_veteran — military service / VA benefits
    # ======================================================================
    op.create_table(
        "case_veteran",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("case_id", sa.String(36), sa.ForeignKey("funeral_cases.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("ever_in_armed_forces", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("branch", sa.String(100), nullable=True),
        # army | navy | marines | air_force | coast_guard | space_force | national_guard
        sa.Column("service_start_date", sa.Date, nullable=True),
        sa.Column("service_end_date", sa.Date, nullable=True),
        sa.Column("service_number", sa.String(100), nullable=True),
        sa.Column("rank", sa.String(100), nullable=True),
        sa.Column("discharge_type", sa.String(100), nullable=True),
        sa.Column("dd214_on_file", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("va_flag_requested", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("va_flag_received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("va_burial_benefits_applied", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("va_burial_benefits_status", sa.String(50), nullable=True),
        sa.Column("military_honors_requested", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ======================================================================
    # 9. case_merchandise — vault, casket, monument, urn, stationery
    # ======================================================================
    op.create_table(
        "case_merchandise",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("case_id", sa.String(36), sa.ForeignKey("funeral_cases.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        # Vault
        sa.Column("vault_product_id", sa.String(36), nullable=True),
        sa.Column("vault_product_name", sa.String(255), nullable=True),
        sa.Column("vault_price", sa.Numeric(10, 2), nullable=True),
        sa.Column("vault_personalization", JSONB, nullable=True),
        sa.Column("vault_design_snapshot_r2_key", sa.String(500), nullable=True),
        sa.Column("vault_approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("vault_approved_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("vault_order_id", sa.String(36), nullable=True),   # cross-tenant ref (FH-1b)
        sa.Column("vault_order_status", sa.String(50), nullable=True),
        # Casket
        sa.Column("casket_product_id", sa.String(36), nullable=True),
        sa.Column("casket_product_name", sa.String(255), nullable=True),
        sa.Column("casket_price", sa.Numeric(10, 2), nullable=True),
        sa.Column("casket_personalization", JSONB, nullable=True),
        sa.Column("casket_design_snapshot_r2_key", sa.String(500), nullable=True),
        sa.Column("casket_approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("casket_approved_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("casket_order_id", sa.String(36), nullable=True),
        sa.Column("casket_order_status", sa.String(50), nullable=True),
        # Monument (FH-1a spec requires monument fields on this table)
        sa.Column("monument_shape", sa.String(50), nullable=True),
        sa.Column("monument_stone", sa.String(100), nullable=True),
        sa.Column("monument_dimensions", JSONB, nullable=True),
        sa.Column("monument_name_text", sa.String(255), nullable=True),
        sa.Column("monument_name_font", sa.String(100), nullable=True),
        sa.Column("monument_dates_text", sa.String(255), nullable=True),
        sa.Column("monument_dates_format", sa.String(50), nullable=True),
        sa.Column("monument_engraving_key", sa.String(200), nullable=True),
        sa.Column("monument_inscription", sa.Text, nullable=True),
        sa.Column("monument_accessories", JSONB, nullable=True),
        sa.Column("monument_design_snapshot_r2_key", sa.String(500), nullable=True),
        sa.Column("monument_approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("monument_approved_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        # Urn (cremation only)
        sa.Column("urn_product_id", sa.String(36), nullable=True),
        sa.Column("urn_product_name", sa.String(255), nullable=True),
        sa.Column("urn_price", sa.Numeric(10, 2), nullable=True),
        sa.Column("urn_personalization", JSONB, nullable=True),
        sa.Column("urn_approved_at", sa.DateTime(timezone=True), nullable=True),
        # Memorial items (stationery, programs, guestbooks, register books)
        sa.Column("memorial_items", JSONB, nullable=True),
        sa.Column("accessories", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ======================================================================
    # 10. case_financials — FTC GPL-compliant itemization
    # ======================================================================
    op.create_table(
        "case_financials",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("case_id", sa.String(36), sa.ForeignKey("funeral_cases.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        # FTC statement of goods and services — JSONB with category keys
        # Structure: {professional_services: {items:[...], subtotal}, transfer: {...}, embalming: {...}, ...}
        sa.Column("statement_of_goods_services", JSONB, nullable=True),
        sa.Column("subtotal", sa.Numeric(12, 2), nullable=True),
        sa.Column("tax", sa.Numeric(12, 2), nullable=True),
        sa.Column("total", sa.Numeric(12, 2), nullable=True),
        sa.Column("amount_paid", sa.Numeric(12, 2), nullable=True, server_default="0"),
        sa.Column("balance_due", sa.Numeric(12, 2), nullable=True),
        sa.Column("payment_terms", sa.String(255), nullable=True),
        sa.Column("insurance_assignment", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("insurance_company", sa.String(255), nullable=True),
        sa.Column("preneed_applied", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("preneed_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("gpl_version_id", sa.String(36), nullable=True),   # links to price_list_version
        sa.Column("gpl_snapshot_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ======================================================================
    # 11. case_preneed — preneed contract details (optional module)
    # ======================================================================
    op.create_table(
        "case_preneed",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("case_id", sa.String(36), sa.ForeignKey("funeral_cases.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("has_preneed", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("contract_number", sa.String(100), nullable=True),
        sa.Column("contract_date", sa.Date, nullable=True),
        sa.Column("trustee", sa.String(255), nullable=True),
        sa.Column("contract_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("growth_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("total_available", sa.Numeric(12, 2), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ======================================================================
    # 12. case_aftercare — post-service follow-up
    # ======================================================================
    op.create_table(
        "case_aftercare",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("case_id", sa.String(36), sa.ForeignKey("funeral_cases.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("thank_you_cards_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("day_30_check_in_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("month_6_check_in_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("year_1_anniversary_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("grief_resources_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ======================================================================
    # 13. case_notes — all notes including Scribe extractions + director edits
    # ======================================================================
    op.create_table(
        "funeral_case_notes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("case_id", sa.String(36), sa.ForeignKey("funeral_cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("note_type", sa.String(50), nullable=False, server_default="general"),
        # general | scribe_extraction | director_edit | system | family_contact | call_summary
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("author_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("author_name", sa.String(255), nullable=True),   # denormalized for display
        # Structured metadata for extractions / edits
        sa.Column("field_key", sa.String(200), nullable=True),
        sa.Column("old_value", sa.Text, nullable=True),
        sa.Column("new_value", sa.Text, nullable=True),
        sa.Column("confidence", sa.Float, nullable=True),
        sa.Column("extraction_payload", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_funeral_case_notes_case", "funeral_case_notes", ["case_id"])
    op.create_index("ix_funeral_case_notes_type", "funeral_case_notes", ["case_id", "note_type"])

    # ======================================================================
    # 14. case_field_config — per-tenant field visibility + staircase config
    # ======================================================================
    op.create_table(
        "case_field_config",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, unique=True),
        sa.Column("default_state", sa.String(2), nullable=True),   # 'NY'
        sa.Column("dc_fields_enabled", JSONB, nullable=True),       # list of field keys
        sa.Column("veterans_module_enabled", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("preneed_module_enabled", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("cremation_module_enabled", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("monument_step_enabled", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("casket_step_enabled", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("staircase_config", JSONB, nullable=True),   # override default step order
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ======================================================================
    # 15-18: case_vaults, vault_tributes, vault_access_log, casket_products
    # ======================================================================
    op.create_table(
        "case_vaults",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("case_id", sa.String(36), sa.ForeignKey("funeral_cases.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("access_token", sa.String(64), nullable=False, unique=True),
        sa.Column("pin_hash", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_case_vaults_token", "case_vaults", ["access_token"])

    op.create_table(
        "vault_tributes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("case_vault_id", sa.String(36), sa.ForeignKey("case_vaults.id", ondelete="CASCADE"), nullable=False),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("author_name", sa.String(255), nullable=False),
        sa.Column("author_relationship", sa.String(100), nullable=True),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        # pending | approved | rejected
        sa.Column("submitted_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("moderated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("moderated_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
    )
    op.create_index("ix_vault_tributes_vault", "vault_tributes", ["case_vault_id"])

    op.create_table(
        "vault_access_log",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("case_vault_id", sa.String(36), sa.ForeignKey("case_vaults.id", ondelete="CASCADE"), nullable=False),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("accessed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column("access_type", sa.String(20), nullable=False),   # pin | token | director
    )
    op.create_index("ix_vault_access_log_vault", "vault_access_log", ["case_vault_id"])

    op.create_table(
        "casket_products",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("supplier", sa.String(50), nullable=False, server_default="other"),
        # batesville | matthews | wilbert | other
        sa.Column("model_name", sa.String(255), nullable=False),
        sa.Column("model_number", sa.String(100), nullable=True),
        sa.Column("sku", sa.String(100), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("price", sa.Numeric(10, 2), nullable=True),
        sa.Column("cost", sa.Numeric(10, 2), nullable=True),
        sa.Column("image_url", sa.String(500), nullable=True),
        sa.Column("catalog_url", sa.String(500), nullable=True),
        # Tier 2: Playwright order URL; Tier 3: Wilbert cross-tenant FK
        sa.Column("playwright_order_url", sa.String(500), nullable=True),
        sa.Column("wilbert_company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_casket_products_company", "casket_products", ["company_id"])


def downgrade() -> None:
    for t in [
        "casket_products",
        "vault_access_log",
        "vault_tributes",
        "case_vaults",
        "case_field_config",
        "funeral_case_notes",
        "case_aftercare",
        "case_preneed",
        "case_financials",
        "case_merchandise",
        "case_veteran",
        "case_cremation",
        "case_cemetery",
        "case_disposition",
        "case_service",
        "case_informants",
        "case_deceased",
        "funeral_cases",
    ]:
        op.drop_table(t)
