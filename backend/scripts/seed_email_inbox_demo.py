"""Seed sample inbox threads on existing email accounts —
Phase W-4b Layer 1 Step 4a.

Builds on Step 1's seed_email_demo.py (which creates the EmailAccount
records) by adding sample inbound threads + messages so the new
``/inbox`` UI has content to render. Idempotent — re-running creates
zero new threads if the canonical sample subjects already exist on
the target accounts.

Sample threads on Sunnycrest sales@:
  1. Hopkins FH — Anderson case follow-up (cross-tenant if Hopkins seeded)
  2. Sunnyvale Cemetery — vault delivery question
  3. Internal — quote update from a teammate

Sample on Hopkins director@ (when seeded):
  1. Sunnycrest manufacturing — vault confirmed (cross-tenant)
  2. Smith family — service follow-up

Usage (from backend/):
    DATABASE_URL=postgresql://localhost:5432/bridgeable_dev \\
        python -m scripts.seed_email_inbox_demo            # dry-run
    DATABASE_URL=postgresql://localhost:5432/bridgeable_dev \\
        python -m scripts.seed_email_inbox_demo --apply
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, BACKEND_DIR)


from app.database import SessionLocal  # noqa: E402
from app.models.email_primitive import (  # noqa: E402
    EmailAccount,
    EmailThread,
)
from app.services.email.ingestion import ingest_provider_message  # noqa: E402
from app.services.email.providers.base import ProviderFetchedMessage  # noqa: E402


_SUNNYCREST_THREADS = [
    {
        "tenant_slug": "testco",
        "account_email": "sales@sunnycrest.test",
        "messages": [
            {
                "subject": "Anderson case — vault delivery confirmation needed",
                "sender_email": "director@hopkinsfh.test",
                "sender_name": "Mary Hopkins",
                "body_text": (
                    "Hi Sunnycrest team —\n\n"
                    "Following up on the Anderson case (FC-2026-0001). "
                    "Family has confirmed Friday 10am for the service. "
                    "Can you confirm the bronze vault is ready for "
                    "delivery to St. Mary's Cemetery by 8am Friday?\n\n"
                    "Thanks,\nMary"
                ),
                "received_offset_minutes": -120,
            },
        ],
    },
    {
        "tenant_slug": "testco",
        "account_email": "sales@sunnycrest.test",
        "messages": [
            {
                "subject": "Quote update — Smith family vault",
                "sender_email": "ops@sunnyvale-cem.test",
                "sender_name": "Sunnyvale Cemetery",
                "body_text": (
                    "Hi —\n\n"
                    "Smith family selected the standard concrete vault "
                    "(quoted last week at $1,200). Please send updated "
                    "invoice when ready.\n\n"
                    "— Sunnyvale Operations"
                ),
                "received_offset_minutes": -360,
            },
        ],
    },
    {
        "tenant_slug": "testco",
        "account_email": "sales@sunnycrest.test",
        "messages": [
            {
                "subject": "Production schedule — week of May 12",
                "sender_email": "production@testco.com",
                "sender_name": "James Atkinson",
                "body_text": (
                    "Team —\n\n"
                    "Here's the production schedule for the week of "
                    "May 12. Three vaults Tuesday, two Wednesday, "
                    "one Thursday. Friday open for emergencies.\n\n"
                    "James"
                ),
                "received_offset_minutes": -1440,
            },
        ],
    },
]


_HOPKINS_THREADS = [
    {
        "tenant_slug": "hopkins-fh",
        "account_email": "director@hopkinsfh.test",
        "messages": [
            {
                "subject": "Re: Anderson case — vault delivery confirmation needed",
                "sender_email": "sales@sunnycrest.test",
                "sender_name": "Sunnycrest Sales",
                "body_text": (
                    "Hi Mary —\n\n"
                    "Confirmed. Bronze vault for Anderson family will "
                    "deliver to St. Mary's by 7:45am Friday. Driver is "
                    "James A.\n\n"
                    "— Sunnycrest"
                ),
                "received_offset_minutes": -90,
            },
        ],
    },
    {
        "tenant_slug": "hopkins-fh",
        "account_email": "director@hopkinsfh.test",
        "messages": [
            {
                "subject": "Smith family — service follow-up",
                "sender_email": "informant@smith-family.test",
                "sender_name": "Patricia Smith",
                "body_text": (
                    "Hello —\n\n"
                    "Following up on Mom's service. Could we add 2 more "
                    "memorial cards? Total now needs to be 75.\n\n"
                    "Thanks,\nPatricia"
                ),
                "received_offset_minutes": -240,
            },
        ],
    },
]


def _build_provider_message(spec: dict, *, base_id: str) -> ProviderFetchedMessage:
    received = datetime.now(timezone.utc) + timedelta(
        minutes=spec.get("received_offset_minutes", 0)
    )
    return ProviderFetchedMessage(
        provider_message_id=base_id,
        provider_thread_id=None,
        sender_email=spec["sender_email"],
        sender_name=spec.get("sender_name"),
        to=[("recipient@bridgeable.test", None)],  # placeholder
        subject=spec["subject"],
        body_text=spec.get("body_text"),
        body_html=None,
        sent_at=received,
        received_at=received,
        in_reply_to_provider_id=None,
        raw_payload={"step_4a_seed": True},
        attachments=[],
    )


def _resolve_account(db, *, tenant_slug: str, email: str):
    from app.models.company import Company

    company = (
        db.query(Company).filter(Company.slug == tenant_slug).first()
    )
    if not company:
        return None
    return (
        db.query(EmailAccount)
        .filter(
            EmailAccount.tenant_id == company.id,
            EmailAccount.email_address == email,
            EmailAccount.is_active.is_(True),
        )
        .first()
    )


def seed(*, apply: bool) -> dict:
    db = SessionLocal()
    summary = {
        "threads_created": 0,
        "threads_skipped": 0,
        "accounts_missing": 0,
    }
    try:
        for thread_spec in _SUNNYCREST_THREADS + _HOPKINS_THREADS:
            account = _resolve_account(
                db,
                tenant_slug=thread_spec["tenant_slug"],
                email=thread_spec["account_email"],
            )
            if not account:
                summary["accounts_missing"] += 1
                continue

            for i, msg_spec in enumerate(thread_spec["messages"]):
                # Idempotency check by subject + account
                existing = (
                    db.query(EmailThread)
                    .filter(
                        EmailThread.account_id == account.id,
                        EmailThread.subject == msg_spec["subject"],
                    )
                    .first()
                )
                if existing:
                    summary["threads_skipped"] += 1
                    continue

                if not apply:
                    print(
                        f"  [dry-run] {thread_spec['account_email']}: "
                        f"would create thread '{msg_spec['subject']}'"
                    )
                    summary["threads_created"] += 1
                    continue

                base_id = f"seed-{account.id[:8]}-{i}-{abs(hash(msg_spec['subject'])) % 100000}"
                msg = ingest_provider_message(
                    db,
                    account=account,
                    provider_message=_build_provider_message(msg_spec, base_id=base_id),
                )
                print(
                    f"  [created] {thread_spec['account_email']}: "
                    f"'{msg_spec['subject']}' "
                    f"(thread={msg.thread_id[:8]} msg={msg.id[:8]})"
                )
                summary["threads_created"] += 1

        if apply:
            db.commit()
        else:
            db.rollback()
    finally:
        db.close()
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Commit the seed data (omit for dry-run).",
    )
    args = parser.parse_args()

    if not os.environ.get("DATABASE_URL"):
        print("ERROR: DATABASE_URL required.", file=sys.stderr)
        return 1
    if os.environ.get("ENVIRONMENT") == "production":
        print("ERROR: refusing to run demo seed against production.", file=sys.stderr)
        return 2

    print(f"Seeding inbox demo threads (apply={args.apply})…\n")
    summary = seed(apply=args.apply)
    print("\n── Summary ─────────────────────────────")
    print(f"  Threads created:  {summary['threads_created']}")
    print(f"  Threads skipped:  {summary['threads_skipped']}")
    print(f"  Accounts missing: {summary['accounts_missing']}")
    print(
        f"\n{'COMMITTED.' if args.apply else 'Dry run — pass --apply to commit.'}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
