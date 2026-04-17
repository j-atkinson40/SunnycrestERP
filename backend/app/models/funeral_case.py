"""Funeral Home case model + 13 satellite tables + 4 vault tables + casket_products."""

import uuid
from datetime import datetime, timezone, date, time
from decimal import Decimal

from sqlalchemy import (
    Boolean, Date, DateTime, Float, ForeignKey, Integer, LargeBinary,
    Numeric, String, Text, Time,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


# ─────────────────────────────────────────────────────────────────────────
# Root case record
# ─────────────────────────────────────────────────────────────────────────
class FuneralCase(Base):
    __tablename__ = "funeral_cases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False)
    location_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("locations.id"), nullable=True)
    case_number: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="active")
    director_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    current_step: Mapped[str] = mapped_column(String(100), nullable=False, default="arrangement_conference")
    completed_steps: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    story_thread_status: Mapped[str | None] = mapped_column(String(50), default="building")
    story_thread_narrative: Mapped[str | None] = mapped_column(Text, nullable=True)
    story_thread_compiled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    all_selections_approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    transcript_r2_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    vault_manufacturer_company_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("companies.id"), nullable=True)
    cemetery_company_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("companies.id"), nullable=True)
    crematory_company_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("companies.id"), nullable=True)
    casket_manufacturer_company_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("companies.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


# ─────────────────────────────────────────────────────────────────────────
# Domain satellites
# ─────────────────────────────────────────────────────────────────────────
class CaseDeceased(Base):
    __tablename__ = "case_deceased"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id: Mapped[str] = mapped_column(String(36), ForeignKey("funeral_cases.id", ondelete="CASCADE"), nullable=False, unique=True)
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False)
    first_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    middle_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    suffix: Mapped[str | None] = mapped_column(String(20), nullable=True)
    maiden_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    aka: Mapped[str | None] = mapped_column(String(255), nullable=True)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    birthplace_city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    birthplace_state: Mapped[str | None] = mapped_column(String(50), nullable=True)
    birthplace_country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    sex: Mapped[str | None] = mapped_column(String(20), nullable=True)
    race: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    ethnicity: Mapped[str | None] = mapped_column(String(100), nullable=True)
    marital_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    religion: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ssn_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    ssn_last_four: Mapped[str | None] = mapped_column(String(4), nullable=True)
    date_of_death: Mapped[date | None] = mapped_column(Date, nullable=True)
    time_of_death: Mapped[time | None] = mapped_column(Time, nullable=True)
    place_of_death_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    place_of_death_city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    place_of_death_state: Mapped[str | None] = mapped_column(String(50), nullable=True)
    place_of_death_zip: Mapped[str | None] = mapped_column(String(20), nullable=True)
    cause_of_death: Mapped[str | None] = mapped_column(Text, nullable=True)
    manner_of_death: Mapped[str | None] = mapped_column(String(50), nullable=True)
    residence_address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    residence_city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    residence_state: Mapped[str | None] = mapped_column(String(50), nullable=True)
    residence_zip: Mapped[str | None] = mapped_column(String(20), nullable=True)
    residence_county: Mapped[str | None] = mapped_column(String(100), nullable=True)
    residence_country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    occupation: Mapped[str | None] = mapped_column(String(255), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(255), nullable=True)
    years_worked: Mapped[int | None] = mapped_column(Integer, nullable=True)
    education_level: Mapped[str | None] = mapped_column(String(100), nullable=True)
    father_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    father_birthplace: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mother_maiden_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mother_birthplace: Mapped[str | None] = mapped_column(String(255), nullable=True)
    spouse_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    spouse_still_living: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    field_confidence: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class CaseInformant(Base):
    __tablename__ = "case_informants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id: Mapped[str] = mapped_column(String(36), ForeignKey("funeral_cases.id", ondelete="CASCADE"), nullable=False)
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    relationship: Mapped[str | None] = mapped_column(String(100), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    is_authorizing: Mapped[bool] = mapped_column(Boolean, default=False)
    authorization_signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    authorization_method: Mapped[str | None] = mapped_column(String(50), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class CaseService(Base):
    __tablename__ = "case_service"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id: Mapped[str] = mapped_column(String(36), ForeignKey("funeral_cases.id", ondelete="CASCADE"), nullable=False, unique=True)
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False)
    service_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    service_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    service_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    service_location_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    service_location_address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    officiant_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    officiant_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    visitation_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    visitation_start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    visitation_end_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    visitation_location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    pallbearers: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    honorary_pallbearers: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    music_selections: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    readings: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    special_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    obituary_draft: Mapped[str | None] = mapped_column(Text, nullable=True)
    obituary_final: Mapped[str | None] = mapped_column(Text, nullable=True)
    obituary_published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    obituary_newspapers: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class CaseDisposition(Base):
    __tablename__ = "case_disposition"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id: Mapped[str] = mapped_column(String(36), ForeignKey("funeral_cases.id", ondelete="CASCADE"), nullable=False, unique=True)
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False)
    disposition_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    death_certificate_status: Mapped[str | None] = mapped_column(String(50), default="not_filed")
    death_certificate_filed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    death_certificate_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    death_certificate_certified_copies_count: Mapped[int | None] = mapped_column(Integer, default=0)
    burial_permit_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    burial_permit_issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class CaseCemetery(Base):
    __tablename__ = "case_cemetery"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id: Mapped[str] = mapped_column(String(36), ForeignKey("funeral_cases.id", ondelete="CASCADE"), nullable=False, unique=True)
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False)
    cemetery_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cemetery_address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    section: Mapped[str | None] = mapped_column(String(50), nullable=True)
    row: Mapped[str | None] = mapped_column(String(50), nullable=True)
    plot_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    plot_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    plot_reserved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    plot_payment_status: Mapped[str | None] = mapped_column(String(50), default="unpaid")
    plot_payment_transaction_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    opening_closing_scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    grave_marker_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class CaseCremation(Base):
    __tablename__ = "case_cremation"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id: Mapped[str] = mapped_column(String(36), ForeignKey("funeral_cases.id", ondelete="CASCADE"), nullable=False, unique=True)
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False)
    crematory_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    crematory_address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    authorization_signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cremation_scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cremation_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cremation_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    urn_selected: Mapped[bool] = mapped_column(Boolean, default=False)
    urn_product_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    disposition_of_ashes: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class CaseVeteran(Base):
    __tablename__ = "case_veteran"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id: Mapped[str] = mapped_column(String(36), ForeignKey("funeral_cases.id", ondelete="CASCADE"), nullable=False, unique=True)
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False)
    ever_in_armed_forces: Mapped[bool] = mapped_column(Boolean, default=False)
    branch: Mapped[str | None] = mapped_column(String(100), nullable=True)
    service_start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    service_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    service_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    rank: Mapped[str | None] = mapped_column(String(100), nullable=True)
    discharge_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    dd214_on_file: Mapped[bool] = mapped_column(Boolean, default=False)
    va_flag_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    va_flag_received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    va_burial_benefits_applied: Mapped[bool] = mapped_column(Boolean, default=False)
    va_burial_benefits_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    military_honors_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class CaseMerchandise(Base):
    __tablename__ = "case_merchandise"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id: Mapped[str] = mapped_column(String(36), ForeignKey("funeral_cases.id", ondelete="CASCADE"), nullable=False, unique=True)
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False)
    # Vault
    vault_product_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    vault_product_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    vault_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    vault_personalization: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    vault_design_snapshot_r2_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    vault_approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    vault_approved_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    vault_order_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    vault_order_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Casket
    casket_product_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    casket_product_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    casket_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    casket_personalization: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    casket_design_snapshot_r2_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    casket_approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    casket_approved_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    casket_order_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    casket_order_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Monument
    monument_shape: Mapped[str | None] = mapped_column(String(50), nullable=True)
    monument_stone: Mapped[str | None] = mapped_column(String(100), nullable=True)
    monument_dimensions: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    monument_name_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    monument_name_font: Mapped[str | None] = mapped_column(String(100), nullable=True)
    monument_dates_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    monument_dates_format: Mapped[str | None] = mapped_column(String(50), nullable=True)
    monument_engraving_key: Mapped[str | None] = mapped_column(String(200), nullable=True)
    monument_inscription: Mapped[str | None] = mapped_column(Text, nullable=True)
    monument_accessories: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    monument_design_snapshot_r2_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    monument_approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    monument_approved_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    # Urn
    urn_product_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    urn_product_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    urn_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    urn_personalization: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    urn_approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Extras
    memorial_items: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    accessories: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class CaseFinancials(Base):
    __tablename__ = "case_financials"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id: Mapped[str] = mapped_column(String(36), ForeignKey("funeral_cases.id", ondelete="CASCADE"), nullable=False, unique=True)
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False)
    statement_of_goods_services: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    subtotal: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    tax: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    total: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    amount_paid: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), default=0)
    balance_due: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    payment_terms: Mapped[str | None] = mapped_column(String(255), nullable=True)
    insurance_assignment: Mapped[bool] = mapped_column(Boolean, default=False)
    insurance_company: Mapped[str | None] = mapped_column(String(255), nullable=True)
    preneed_applied: Mapped[bool] = mapped_column(Boolean, default=False)
    preneed_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    gpl_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    gpl_snapshot_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class CasePreneed(Base):
    __tablename__ = "case_preneed"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id: Mapped[str] = mapped_column(String(36), ForeignKey("funeral_cases.id", ondelete="CASCADE"), nullable=False, unique=True)
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False)
    has_preneed: Mapped[bool] = mapped_column(Boolean, default=False)
    contract_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    contract_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    trustee: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contract_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    growth_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    total_available: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class CaseAftercare(Base):
    __tablename__ = "case_aftercare"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id: Mapped[str] = mapped_column(String(36), ForeignKey("funeral_cases.id", ondelete="CASCADE"), nullable=False, unique=True)
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False)
    thank_you_cards_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    day_30_check_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    month_6_check_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    year_1_anniversary_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    grief_resources_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class FuneralCaseNote(Base):
    __tablename__ = "funeral_case_notes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id: Mapped[str] = mapped_column(String(36), ForeignKey("funeral_cases.id", ondelete="CASCADE"), nullable=False)
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False)
    note_type: Mapped[str] = mapped_column(String(50), default="general")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    author_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    author_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    field_key: Mapped[str | None] = mapped_column(String(200), nullable=True)
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    extraction_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class CaseFieldConfig(Base):
    __tablename__ = "case_field_config"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False, unique=True)
    default_state: Mapped[str | None] = mapped_column(String(2), nullable=True)
    dc_fields_enabled: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    veterans_module_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    preneed_module_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    cremation_module_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    monument_step_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    casket_step_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    staircase_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


# ─────────────────────────────────────────────────────────────────────────
# Vault (funeral-home-facing) + tributes + access log
# ─────────────────────────────────────────────────────────────────────────
class FHCaseVault(Base):
    __tablename__ = "case_vaults"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id: Mapped[str] = mapped_column(String(36), ForeignKey("funeral_cases.id", ondelete="CASCADE"), nullable=False, unique=True)
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False)
    access_token: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    pin_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class VaultTribute(Base):
    __tablename__ = "vault_tributes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    case_vault_id: Mapped[str] = mapped_column(String(36), ForeignKey("case_vaults.id", ondelete="CASCADE"), nullable=False)
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False)
    author_name: Mapped[str] = mapped_column(String(255), nullable=False)
    author_relationship: Mapped[str | None] = mapped_column(String(100), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending")
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    moderated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    moderated_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)


class VaultAccessLog(Base):
    __tablename__ = "vault_access_log"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    case_vault_id: Mapped[str] = mapped_column(String(36), ForeignKey("case_vaults.id", ondelete="CASCADE"), nullable=False)
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False)
    accessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    access_type: Mapped[str] = mapped_column(String(20), nullable=False)


# ─────────────────────────────────────────────────────────────────────────
# Casket products
# ─────────────────────────────────────────────────────────────────────────
class CasketProduct(Base):
    __tablename__ = "casket_products"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False)
    supplier: Mapped[str] = mapped_column(String(50), default="other")
    model_name: Mapped[str] = mapped_column(String(255), nullable=False)
    model_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    sku: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    cost: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    catalog_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    playwright_order_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    wilbert_company_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("companies.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
