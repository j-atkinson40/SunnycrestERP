import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, backref, mapped_column, relationship

from app.database import Base


class Invoice(Base):
    """Customer invoice — generated from a sales order or standalone."""

    __tablename__ = "invoices"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False, index=True
    )
    number: Mapped[str] = mapped_column(String(50), nullable=False)  # INV-YYYY-####
    customer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("customers.id"), nullable=False, index=True
    )
    sales_order_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("sales_orders.id"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="draft"
    )  # draft, sent, paid, partial, overdue, void, write_off

    invoice_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    due_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    payment_terms: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Amounts
    subtotal: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    tax_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 4), nullable=False, default=Decimal("0.00")
    )
    tax_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    total: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    amount_paid: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    # Exceptions arc: credit memos reduce the balance without pretending
    # to be payments; a write-off moves the remainder off AR with its
    # reason. balance_remaining derives from all three.
    amount_credited: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00"), server_default="0"
    )
    written_off_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00"), server_default="0"
    )
    write_off_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Finance-charge marker (column existed in every DB; the model never
    # declared it — same born-dormant class as the FC customer columns.
    # Declared in the sales-tax arc: the accumulator excludes FC
    # invoices, and the FC posting path's Invoice(is_finance_charge=True)
    # kwarg now actually works).
    is_finance_charge: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    # Sales-tax filing facts (structured sources for the accumulator).
    # History stays NULL and is classified honestly as unclassified.
    tax_source: Mapped[str | None] = mapped_column(String(40), nullable=True)
    tax_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    tax_jurisdiction: Mapped[str | None] = mapped_column(String(120), nullable=True)
    exempt_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00"), server_default="0"
    )

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Payment tracking
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"), server_default="0.00")
    discount_deadline: Mapped[date | None] = mapped_column(Date(), nullable=True)
    discounted_total: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)

    # Deceased name — copied from order at invoice creation, shown on PDF
    deceased_name: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Email delivery tracking
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_to_email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    sage_invoice_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    qbo_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True, index=True
    )

    # Review workflow — set on auto-generated drafts
    requires_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    review_due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    auto_generated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    generation_reason: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # 'end_of_day_batch' | 'immediate' | 'manual'
    has_exceptions: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    approved_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Consolidated billing
    is_consolidated: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    is_split_payment: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    group_company_entity_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("company_entities.id"), nullable=True
    )
    parent_invoice_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("invoices.id"), nullable=True
    )

    # INV-1 A-2 (r170) — the entry that booked `Dr AR / Cr revenue`, or NULL.
    #
    # NULL is a real and expected state, not a gap waiting to be filled. The
    # decided discipline is fail-closed on the LEDGER and fail-open on the
    # RECORD: an invoice issues even when no revenue account is configured, so
    # this column is what makes "which invoices are unposted" answerable at all.
    #
    # FK'd, per r153/r154/r155 — deleting an entry an issued invoice points at
    # should be refused, not silently unlink it and leave the invoice looking
    # unposted. The unconstrained `discount_journal_entry_id` (q2l3) is the
    # counter-example, and AR-0.1 already records it as an open question.
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

    @hybrid_property
    def balance_remaining(self) -> Decimal:
        """What this invoice still owes: total − paid − credited − written off.

        A HYBRID, not a plain property, and that is the whole point (AR-1 C-3).

        Before this, the four-term truth lived here in Python and could not be
        used in SQL, so every aggregating caller re-implemented it and they
        drifted: the nightly sweeper computed three terms (dropping
        `written_off_amount`) under a comment promising to "keep this formula in
        lockstep with the model property", and fifteen dashboard/report sites
        computed two (dropping credits AND write-offs). A comment asking two
        expressions to agree is not a mechanism. A hybrid makes them the same
        expression, compiled to Python for `inv.balance_remaining` and to SQL
        for `func.sum(Invoice.balance_remaining)`.

        Same principle as `_count_membership` (queue-count seam), `_count_config`
        and `KeywordPostingContext.decide` — one definition, multiple consumers,
        cannot diverge. `hybrid_property` is a new mechanism in this codebase;
        the pattern is not.

        THE PARTIALLY WRITTEN-OFF INVOICE IS WHY ALL FOUR TERMS ARE HERE. It
        keeps its ordinary status, so no status filter can correct it — the
        three-term formula counts the written-off portion as still owed and the
        two-term formula counts the written-off AND credited portions. Only the
        terms fix the terms. Membership (`services/ar_balance.py`) answers
        whether this is a live receivable document; this answers how much.
        Neither needs to know about the other.

        ⚠️ THE PYTHON BRANCH'S CORRECTNESS DEPENDS ON ALL FOUR COLUMNS STAYING
        NOT NULL. They are today — verified against `information_schema`:
        `total`, `amount_paid`, `amount_credited` and `written_off_amount` are
        all NOT NULL with defaults. The previous property carried
        `or Decimal("0.00")` defenses that could never fire; they are dropped
        rather than mirrored into the SQL branch, because defensive code that
        cannot execute reads as load-bearing and would have made the two
        branches structurally different for no reason. A migration making any of
        these nullable must add `COALESCE` to BOTH branches.
        """
        return (
            self.total
            - self.amount_paid
            - self.amount_credited
            - self.written_off_amount
        )

    @balance_remaining.expression
    def balance_remaining(cls):  # noqa: N805 - SQLAlchemy hybrid convention
        """The SQL half of the same expression. No COALESCE: see the note on
        NOT NULL above."""
        return (
            cls.total
            - cls.amount_paid
            - cls.amount_credited
            - cls.written_off_amount
        )

    # Relationships
    company = relationship("Company")
    customer = relationship("Customer")
    sales_order = relationship("SalesOrder", back_populates="invoices")
    lines = relationship(
        "InvoiceLine", back_populates="invoice", order_by="InvoiceLine.sort_order"
    )
    payment_applications = relationship(
        "CustomerPaymentApplication", back_populates="invoice"
    )
    creator = relationship("User", foreign_keys=[created_by])
    billing_group = relationship("CompanyEntity", foreign_keys=[group_company_entity_id])
    child_invoices = relationship(
        "Invoice",
        foreign_keys=[parent_invoice_id],
        backref=backref("parent_invoice", remote_side="Invoice.id"),
    )


class InvoiceLine(Base):
    __tablename__ = "invoice_lines"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    invoice_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("invoices.id"), nullable=False, index=True
    )
    product_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("products.id"), nullable=True
    )
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(12, 4), nullable=False, default=Decimal("1")
    )
    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(12, 4), nullable=False, default=Decimal("0.00")
    )
    line_total: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    invoice = relationship("Invoice", back_populates="lines")
    product = relationship("Product")
