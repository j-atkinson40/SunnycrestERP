import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class CustomerPayment(Base):
    """Customer payment — applied across one or more invoices."""

    __tablename__ = "customer_payments"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False, index=True
    )
    customer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("customers.id"), nullable=False, index=True
    )
    payment_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False
    )
    payment_method: Mapped[str] = mapped_column(
        String(30), nullable=False, default="check"
    )  # check, ach, credit_card, cash, wire
    reference_number: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    sage_payment_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    qbo_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True, index=True
    )

    # Early payment discount. THE SCHEMA WAS NEVER MISSING — migration
    # `q2l3m4n5o6p7_add_early_payment_discount` created all seven of these
    # columns when EPD shipped. THE MODEL was missing them, which is a quieter
    # and more dangerous failure: `apply_discounted_payment` assigned all seven,
    # SQLAlchemy accepted each as an unmapped INSTANCE attribute, the commit
    # succeeded, and every value evaporated at the end of the request while the
    # columns sat empty in a table that had room for them all along.
    #
    # What was being lost: which payments were discounted, by how much, at what
    # rate, under a policy rule or a MANAGER OVERRIDE, by which manager, for
    # what stated reason, and which journal entry backed the concession.
    #
    # These declarations MIRROR q2l3 exactly — Numeric(12,2) not (14,2),
    # String(20) not (30), every column NULLABLE with q2l3's server_defaults.
    # A model that disagrees with its table is how this class of bug starts;
    # widening a type here would have been a second opinion about the schema,
    # not a fix. If these types are wrong, the migration is the place to say so.
    discount_applied: Mapped[bool | None] = mapped_column(
        Boolean, nullable=True, server_default=text("false"), default=False
    )
    discount_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True, server_default=text("0")
    )
    # The RATE (2.00 = 2%), kept separate from the amount on purpose: the rate
    # is the policy, the amount is its application to one balance. Recomputing
    # either from the other loses the rounding actually granted.
    discount_percentage: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2), nullable=True
    )
    discount_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # NO ForeignKey on either id column: q2l3 created both as bare VARCHAR(36)
    # with no constraint, and adding one here would make the ORM assert a
    # relationship the database does not enforce. Whether they SHOULD be FKs is
    # a real question (an entry a discounted payment points at should not be
    # deletable) and it belongs in a migration, not in a model annotation.
    discount_override_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    discount_override_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    discount_journal_entry_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True
    )

    # AR-2 (r155): the entry that booked the RECEIPT — Dr bank / Cr AR. Distinct
    # from `discount_journal_entry_id` above, which books the DISCOUNT; a
    # discounted payment has two entries and keeping the links separate means
    # neither has to be interpreted by which arc wrote it.
    #
    # NULL is an expected, recoverable state, not a defect: the decided
    # discipline is that a payment RECORDS even when it cannot post (a payment
    # is an event that already happened), so this column is what makes "which
    # payments are unposted" answerable at all.
    #
    # FK'd, unlike its q2l3 sibling — deleting an entry a payment points at
    # should be refused, per r153/r154.
    journal_entry_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("journal_entries.id"), nullable=True
    )

    # Audit
    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    modified_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    modified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # N-1+2 (r156). A RETURNED payment is not a voided one: the void says this
    # should never have been recorded and soft-deletes the row; the return says
    # it happened and the bank took it back, so the row SURVIVES carrying the
    # mark. Load-bearing rather than decorative — `void_payment`'s unwind leaves
    # the CustomerPaymentApplication rows in place and only adjusts the invoices
    # they point at, so an unmarked reversed payment would read as live and
    # applied while its invoices no longer reflect it.
    returned_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    returned_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    company = relationship("Company")
    customer = relationship("Customer")
    applications = relationship(
        "CustomerPaymentApplication", back_populates="payment"
    )
    creator = relationship("User", foreign_keys=[created_by])


class CustomerPaymentApplication(Base):
    """Maps a payment to one or more invoices.

    NOTE FOR TEST TEARDOWN: rows here reference customer_payments AND invoices
    (no ondelete=CASCADE on either FK). Any marker-scoped teardown that deletes
    W2/test payments or invoices must delete the applications FIRST. See
    scripts/seed_reconciliation_test.cleanup_existing — the Arc B Accept flow
    creates these rows (payment→invoice application), which the seed itself never
    does, so the gap only surfaces after an Accept has run against the fixture.
    """

    __tablename__ = "customer_payment_applications"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    payment_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("customer_payments.id"), nullable=False, index=True
    )
    invoice_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("invoices.id"), nullable=False, index=True
    )
    amount_applied: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    payment = relationship("CustomerPayment", back_populates="applications")
    invoice = relationship("Invoice", back_populates="payment_applications")
