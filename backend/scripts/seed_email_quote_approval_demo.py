"""Seed a sample quote_approval email with magic-link token —
Phase W-4b Layer 1 Step 4c.

Demonstrates the kill-the-portal canonical case (BRIDGEABLE_MASTER
§3.26.15.17). Creates:
  - A sample Quote on the testco tenant for Hopkins FH
  - An outbound EmailMessage from sales@sunnycrest.test to
    director@hopkinsfh.test carrying the canonical quote_approval
    action in message_payload
  - An email_action_tokens row so the magic-link surface resolves
  - Both inline-action UX (visible in /email when admin opens the
    thread) AND magic-link UX (visit /email/actions/{token}) work
    end-to-end against the same action

Idempotent — skips if a sample Quote with the demo number exists.

Usage (from backend/):
    DATABASE_URL=postgresql://localhost:5432/bridgeable_dev \\
        python -m scripts.seed_email_quote_approval_demo            # dry-run
    DATABASE_URL=postgresql://localhost:5432/bridgeable_dev \\
        python -m scripts.seed_email_quote_approval_demo --apply
"""

from __future__ import annotations

import argparse
import os
import sys
import uuid
from datetime import datetime, timezone
from decimal import Decimal


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, BACKEND_DIR)


from app.database import SessionLocal  # noqa: E402
from app.models.company import Company  # noqa: E402
from app.models.email_primitive import (  # noqa: E402
    EmailAccount,
    EmailMessage,
    EmailThread,
)
from app.models.quote import Quote, QuoteLine  # noqa: E402
from app.services.email.email_action_service import (  # noqa: E402
    build_quote_approval_action,
    issue_action_token,
)


_DEMO_QUOTE_NUMBER = "QTE-DEMO-4C"
_DEMO_THREAD_SUBJECT = "Quote QTE-DEMO-4C — Anderson family vault"


def _resolve_tenant(db, slug: str) -> Company | None:
    return db.query(Company).filter(Company.slug == slug).first()


def _resolve_account(db, tenant_id: str, email: str) -> EmailAccount | None:
    return (
        db.query(EmailAccount)
        .filter(
            EmailAccount.tenant_id == tenant_id,
            EmailAccount.email_address == email,
        )
        .first()
    )


def _existing_demo_quote(db, tenant_id: str) -> Quote | None:
    return (
        db.query(Quote)
        .filter(Quote.company_id == tenant_id, Quote.number == _DEMO_QUOTE_NUMBER)
        .first()
    )


def _create_demo_quote(db, tenant: Company) -> Quote:
    q = Quote(
        id=str(uuid.uuid4()),
        company_id=tenant.id,
        number=_DEMO_QUOTE_NUMBER,
        customer_name="Hopkins Funeral Home",
        status="sent",
        quote_date=datetime.now(timezone.utc),
        subtotal=Decimal("2750.00"),
        tax_rate=Decimal("0.0000"),
        tax_amount=Decimal("0.00"),
        total=Decimal("2750.00"),
        notes="Anderson family vault — bronze top, deluxe lining.",
    )
    db.add(q)
    db.flush()
    db.add(
        QuoteLine(
            id=str(uuid.uuid4()),
            quote_id=q.id,
            description="Bronze burial vault — Anderson family",
            quantity=Decimal("1"),
            unit_price=Decimal("2500.00"),
            line_total=Decimal("2500.00"),
        )
    )
    db.add(
        QuoteLine(
            id=str(uuid.uuid4()),
            quote_id=q.id,
            description="Deluxe interior lining",
            quantity=Decimal("1"),
            unit_price=Decimal("250.00"),
            line_total=Decimal("250.00"),
        )
    )
    db.flush()
    return q


def _create_demo_thread_and_message(
    db, tenant: Company, account: EmailAccount, quote: Quote
) -> tuple[EmailThread, EmailMessage]:
    thread = EmailThread(
        id=str(uuid.uuid4()),
        tenant_id=tenant.id,
        account_id=account.id,
        subject=_DEMO_THREAD_SUBJECT,
        participants_summary=[
            account.email_address.lower(),
            "director@hopkinsfh.test",
        ],
        first_message_at=datetime.now(timezone.utc),
        last_message_at=datetime.now(timezone.utc),
        message_count=1,
    )
    db.add(thread)
    db.flush()

    # Refetch quote with lines so action build can populate line_items
    quote_full = (
        db.query(Quote).filter(Quote.id == quote.id).first()
    )
    action = build_quote_approval_action(quote=quote_full)

    body_html = (
        '<div style="font-family: -apple-system, BlinkMacSystemFont, '
        '\'IBM Plex Sans\', sans-serif; max-width: 580px;">'
        "<p>Hi Mary —</p>"
        "<p>Attached for your approval is the quote for the Anderson "
        "family vault. Total of "
        f"<strong>${quote.total}</strong> covers the bronze vault + "
        "deluxe interior lining.</p>"
        '<p>Please use the action buttons below to approve, request '
        "changes, or decline. Reach out if you have any questions.</p>"
        '<p style="margin-top: 24px;">Best,<br>James Atkinson</p>'
        "</div>"
    )
    body_text = (
        "Hi Mary —\n\n"
        "Attached for your approval is the quote for the Anderson "
        f"family vault. Total of ${quote.total} covers the bronze "
        "vault + deluxe interior lining.\n\n"
        "Please use the action buttons in the email to approve, "
        "request changes, or decline. Reach out with any questions.\n\n"
        "Best,\nJames Atkinson"
    )

    msg = EmailMessage(
        id=str(uuid.uuid4()),
        thread_id=thread.id,
        tenant_id=tenant.id,
        account_id=account.id,
        provider_message_id=f"demo-4c-{uuid.uuid4().hex[:12]}",
        sender_email=account.email_address.lower(),
        sender_name="James Atkinson (Sunnycrest)",
        subject=_DEMO_THREAD_SUBJECT,
        body_html=body_html,
        body_text=body_text,
        sent_at=datetime.now(timezone.utc),
        received_at=datetime.now(timezone.utc),
        direction="outbound",
        message_payload={
            "provider": "demo",
            "actions": [action],
        },
    )
    db.add(msg)
    db.flush()
    return thread, msg


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument(
        "--tenant-slug",
        default="testco",
        help="Tenant slug to seed against (default: testco)",
    )
    parser.add_argument(
        "--from-email",
        default="sales@sunnycrest.test",
        help="Sending account email_address (must already exist)",
    )
    args = parser.parse_args()

    if not os.environ.get("DATABASE_URL"):
        print("ERROR: DATABASE_URL env var required.", file=sys.stderr)
        return 1
    if os.environ.get("ENVIRONMENT") == "production":
        print(
            "ERROR: refusing to run demo seed against production.",
            file=sys.stderr,
        )
        return 2

    print(f"Seeding quote_approval demo (apply={args.apply})…")
    db = SessionLocal()
    try:
        tenant = _resolve_tenant(db, args.tenant_slug)
        if not tenant:
            print(
                f"  [skip] Tenant slug {args.tenant_slug!r} not found. "
                "Run scripts/seed_staging.py first.",
                file=sys.stderr,
            )
            return 3

        account = _resolve_account(db, tenant.id, args.from_email)
        if not account:
            print(
                f"  [skip] EmailAccount {args.from_email!r} not found "
                f"for tenant {tenant.slug!r}. Run "
                "scripts/seed_email_demo.py first.",
                file=sys.stderr,
            )
            return 4

        existing = _existing_demo_quote(db, tenant.id)
        if existing:
            print(
                f"  [skip] Demo Quote {_DEMO_QUOTE_NUMBER!r} already "
                f"exists (id={existing.id[:8]}…). Re-run idempotently."
            )
            return 0

        if not args.apply:
            print(
                "  [dry-run] Would create:\n"
                f"    Quote {_DEMO_QUOTE_NUMBER} ($2,750 to Hopkins FH)\n"
                f"    Outbound email from {account.email_address} "
                "to director@hopkinsfh.test with quote_approval action\n"
                "    Magic-link token (7-day TTL)\n"
                "  Pass --apply to commit."
            )
            return 0

        quote = _create_demo_quote(db, tenant)
        _, message = _create_demo_thread_and_message(
            db, tenant, account, quote
        )
        token = issue_action_token(
            db,
            tenant_id=tenant.id,
            message_id=message.id,
            action_idx=0,
            action_type="quote_approval",
            recipient_email="director@hopkinsfh.test",
        )
        db.commit()

        frontend = os.environ.get("FRONTEND_URL", "http://localhost:5173")
        magic_link = f"{frontend}/email/actions/{token}"
        print(
            f"  [created] Quote {_DEMO_QUOTE_NUMBER}\n"
            f"  [created] EmailMessage {message.id[:8]}…\n"
            f"  [created] Magic-link token (7-day TTL)\n"
            f"\nMagic-link URL (open in fresh browser to test "
            f"non-Bridgeable flow):\n  {magic_link}\n\n"
            f"Inline-action UX: open /email in admin login + select "
            f"thread {_DEMO_THREAD_SUBJECT!r}"
        )
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
