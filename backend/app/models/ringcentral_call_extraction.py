"""RingCentral call extraction — AI-extracted order data from call transcripts."""

import uuid
from datetime import date, datetime, time, timezone

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, String, Text, Time
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class RingCentralCallExtraction(Base):
    __tablename__ = "ringcentral_call_extractions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False, index=True)
    call_log_id: Mapped[str] = mapped_column(String(36), ForeignKey("ringcentral_call_log.id"), nullable=False)
    master_company_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("company_entities.id"), nullable=True)

    # Extracted fields
    funeral_home_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    deceased_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    vault_type: Mapped[str | None] = mapped_column(String(200), nullable=True)
    vault_size: Mapped[str | None] = mapped_column(String(100), nullable=True)
    cemetery_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    burial_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # ⚠️ RENAMED FROM `burial_time` BY r199 (2026-10-06). An order carries TWO time
    # facts and this column held the first of them under the second's name — see
    # `capture/schema.py`'s `service_time` entry for the defect it produced.
    service_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    #: ⚠️ ADDED BY r199. The procession ETA — cemetery arrival. Its destination,
    #: `sales_orders.eta`, predates it and already carried the rule in a comment
    #: ("null for graveside"); nothing captured it until Piece 4.
    eta: Mapped[time | None] = mapped_column(Time, nullable=True)
    #: ⚠️ ADDED BY r199, AND WITHOUT THEM TWO CAPTURE FIELDS WERE DEAD. The template
    #: has asked for `service_location` since 2026-10-05 and this model had no column
    #: for it, so the call path could never answer it — which means `eta` and
    #: `service_location_other`, whose conditions both READ it, would have resolved
    #: INDETERMINATE forever. A conditional field whose dependency is unanswerable is
    #: a field that never applies.
    service_location: Mapped[str | None] = mapped_column(String(20), nullable=True)
    service_location_other: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # ── order capture part 1, r200 (2026-10-07) ──────────────────────────────
    #
    # ⚠️ DECLARED HERE AS WELL AS IN THE MIGRATION, AND THE PRECEDENT FOR FORGETTING
    # IS IN CANON. `products.variant_template_id` was added by r186 and declared on no
    # model, so the link the whole catalog design resolves through was unreachable from
    # the ORM — and CLAUDE.md §5 records that `assert_no_schema_drift` cannot see it,
    # because a DB column the model omits is "DB-extra" and ignored by design. A
    # column that exists only in Postgres is a column no Python can read.
    #
    # The comment three lines up is the same failure already recorded on this very
    # model: `service_location` was asked for by the template from 2026-10-05 with no
    # column here, so the call path could never answer it.
    #
    #: R4. ⚠️ NOT `burial_date`. The service and the burial are two facts and may fall
    #: on different days; `service_time`/`eta` above split the time version of exactly
    #: this conflation in r199.
    service_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    #: R4. Prompted, never required — cemeteries share names across towns.
    cemetery_city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    #: R1. THE ONE personalization answer. Vocabulary lives in
    #: `personalization/questions.py`; no CHECK here, same call as `service_location`.
    personalization: Mapped[str | None] = mapped_column(String(40), nullable=True)
    #: R2 (r202). `standard` | `custom`. ⚠️ `legacy_print_name` below hangs off THIS
    #: field, not off the personalization answer — the portal asks which print only
    #: for standard.
    legacy_series: Mapped[str | None] = mapped_column(String(20), nullable=True)
    #: R3. The print name AS SPOKEN. The resolver turns it into candidates and never
    #: picks, so this column holds the phrase and never the resolution.
    legacy_print_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    #: Which vinyl symbol. ⚠️ Not from a ruling — R1 collapsed the eight symbols out of
    #: the answer set, so without this the family's choice has nowhere to land.
    lifes_reflections_symbol: Mapped[str | None] = mapped_column(
        String(60), nullable=True
    )
    grave_location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    special_requests: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Confidence per field
    confidence_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Missing fields list
    missing_fields: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    #: ⚠️ THE SERVER DECIDES WHAT IS CAPTURED, NOT ONLY WHAT IS MISSING. Added
    #: r197. Its sibling above was persisted from the start; this one was
    #: computed by `capture.evaluate`, written to a single log line and thrown
    #: away — so the client had nothing to render for "captured" and re-derived
    #: it twice, from two disagreeing hardcoded lists. The pair is now
    #: symmetric: the client renders both and derives neither.
    #:
    #: NULL means no answered set was computed for this row, which is not the
    #: same as `[]` ("the capture answered nothing"). See r197's docstring.
    answered_fields: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    #: ⚠️ WHAT THE VAULT PHRASE RESOLVED TO. Added r198. Three outcomes, and the
    #: middle one is why this column exists:
    #:
    #:   {"resolved_variant_id": "...", "candidates": ["BV-CON34"]}
    #:   {"resolved_variant_id": null, "candidates": ["BV-BTRI","UV-BTRI"],
    #:    "discriminator": "form"}          <- ambiguous: a QUESTION, not a failure
    #:   {"resolved_variant_id": null, "candidates": []}
    #:
    #: Without it the ambiguous case reaches the client as an empty capture list,
    #: indistinguishable from no match — which discards the whole reason
    #: `product_name_resolver` returns a set rather than a winner.
    #:
    #: NULL means no resolution was attempted for this row.
    vault_resolution: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Call metadata
    call_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    call_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    urgency: Mapped[str | None] = mapped_column(String(20), nullable=True)
    suggested_callback: Mapped[bool] = mapped_column(Boolean, default=False)

    # Status
    draft_order_created: Mapped[bool] = mapped_column(Boolean, default=False)
    draft_order_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("sales_orders.id"), nullable=True)
    reviewed_by_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    call_log = relationship("RingCentralCallLog", back_populates="extraction")
    draft_order = relationship("SalesOrder", foreign_keys=[draft_order_id])
    company_entity = relationship("CompanyEntity", foreign_keys=[master_company_id])
