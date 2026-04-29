"""Seed Email Primitive demo accounts — Phase W-4b Layer 1 Step 1.

Creates a small set of EmailAccount + EmailAccountAccess records for
the Sunnycrest manufacturing tenant (testco) + Hopkins FH tenant
(if both seeds have already been applied via seed_staging.py +
seed_fh_demo.py). Idempotent: existing accounts (matched by
``(tenant_id, email_address)``) are left untouched.

Demo accounts created:

  Sunnycrest (testco — manufacturing):
    - sales@sunnycrest.test    shared / gmail / admin auto-grants creator
    - dispatch@sunnycrest.test shared / gmail
    - admin's personal account (admin@testco.com via gmail)

  Hopkins FH (hopkins-fh — funeral_home):
    - director@hopkinsfh.test  shared / gmail
    - aftercare@hopkinsfh.test shared / msgraph

All seed accounts use ``provider_type=gmail`` (or msgraph) WITHOUT
real OAuth tokens. The provider_config carries
``{"step_1_seed": true}`` so subsequent steps skip these in real
sync runs. Step 2 wires real OAuth.

Usage (from backend/):
    DATABASE_URL=postgresql://localhost:5432/bridgeable_dev \\
        python -m scripts.seed_email_demo            # dry-run
    DATABASE_URL=postgresql://localhost:5432/bridgeable_dev \\
        python -m scripts.seed_email_demo --apply
"""

from __future__ import annotations

import argparse
import os
import sys

# Bootstrap path so ``app.*`` resolves when run from backend/.
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, BACKEND_DIR)


from app.database import SessionLocal  # noqa: E402
from app.models.company import Company  # noqa: E402
from app.models.email_primitive import (  # noqa: E402
    EmailAccount,
    EmailAccountAccess,
)
from app.models.user import User  # noqa: E402
from app.services.email import account_service  # noqa: E402


_DEMO_PLAN: list[dict] = [
    # Tenant: Sunnycrest (slug=testco; manufacturing).
    {
        "tenant_slug": "testco",
        "admin_email": "admin@testco.com",
        "accounts": [
            {
                "account_type": "shared",
                "display_name": "Sales Inbox",
                "email_address": "sales@sunnycrest.test",
                "provider_type": "gmail",
                "is_default": True,
            },
            {
                "account_type": "shared",
                "display_name": "Dispatch Inbox",
                "email_address": "dispatch@sunnycrest.test",
                "provider_type": "gmail",
                "is_default": False,
            },
            {
                "account_type": "personal",
                "display_name": "Admin (James)",
                "email_address": "admin@testco.com",
                "provider_type": "gmail",
                "is_default": False,
            },
        ],
    },
    # Tenant: Hopkins FH (slug=hopkins-fh; funeral_home). Optional —
    # only seeded if the tenant exists (i.e. seed_fh_demo.py was run).
    {
        "tenant_slug": "hopkins-fh",
        "admin_email": "admin@hopkinsfh.test",
        "accounts": [
            {
                "account_type": "shared",
                "display_name": "Director Inbox",
                "email_address": "director@hopkinsfh.test",
                "provider_type": "gmail",
                "is_default": True,
            },
            {
                "account_type": "shared",
                "display_name": "Aftercare Inbox",
                "email_address": "aftercare@hopkinsfh.test",
                "provider_type": "msgraph",
                "is_default": False,
            },
        ],
    },
]


def seed(*, apply: bool) -> dict[str, int]:
    """Seed the demo accounts.

    Returns a summary dict ``{tenants_seeded, accounts_created,
    accounts_skipped, tenants_missing}``. When ``apply=False`` the
    operations are dry-run (no commits).
    """
    db = SessionLocal()
    summary = {
        "tenants_seeded": 0,
        "accounts_created": 0,
        "accounts_skipped": 0,
        "tenants_missing": 0,
    }
    try:
        for plan in _DEMO_PLAN:
            tenant = (
                db.query(Company)
                .filter(Company.slug == plan["tenant_slug"])
                .first()
            )
            if not tenant:
                print(
                    f"  [skip] Tenant '{plan['tenant_slug']}' not found "
                    f"(run the appropriate base seed first)."
                )
                summary["tenants_missing"] += 1
                continue

            admin = (
                db.query(User)
                .filter(
                    User.company_id == tenant.id,
                    User.email == plan["admin_email"],
                )
                .first()
            )
            if not admin:
                print(
                    f"  [skip] Tenant '{plan['tenant_slug']}' has no admin "
                    f"user '{plan['admin_email']}'."
                )
                summary["tenants_missing"] += 1
                continue

            print(
                f"\nTenant '{plan['tenant_slug']}' (admin={admin.email}):"
            )
            for acc_spec in plan["accounts"]:
                existing = (
                    db.query(EmailAccount)
                    .filter(
                        EmailAccount.tenant_id == tenant.id,
                        EmailAccount.email_address
                        == acc_spec["email_address"],
                    )
                    .first()
                )
                if existing:
                    print(
                        f"  [skip] Account '{acc_spec['email_address']}' "
                        f"already exists (id={existing.id})."
                    )
                    summary["accounts_skipped"] += 1
                    continue

                if not apply:
                    print(
                        f"  [dry-run] Would create '{acc_spec['email_address']}' "
                        f"({acc_spec['provider_type']}, "
                        f"{acc_spec['account_type']})."
                    )
                    summary["accounts_created"] += 1
                    continue

                account = account_service.create_account(
                    db,
                    tenant_id=tenant.id,
                    actor_user_id=admin.id,
                    account_type=acc_spec["account_type"],
                    display_name=acc_spec["display_name"],
                    email_address=acc_spec["email_address"],
                    provider_type=acc_spec["provider_type"],
                    provider_config={"step_1_seed": True},
                    is_default=acc_spec["is_default"],
                )
                # Auto-grant admin access to the creator.
                account_service.grant_access(
                    db,
                    account_id=account.id,
                    tenant_id=tenant.id,
                    user_id=admin.id,
                    access_level="admin",
                    actor_user_id=admin.id,
                )
                print(
                    f"  [created] '{acc_spec['email_address']}' (id={account.id})"
                )
                summary["accounts_created"] += 1
            summary["tenants_seeded"] += 1
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
        help="Actually commit the seed data (omit for dry-run).",
    )
    args = parser.parse_args()

    if not os.environ.get("DATABASE_URL"):
        print(
            "ERROR: DATABASE_URL environment variable is required.",
            file=sys.stderr,
        )
        return 1

    if os.environ.get("ENVIRONMENT") == "production":
        print(
            "ERROR: refusing to run demo seed against production.",
            file=sys.stderr,
        )
        return 2

    print(
        "Seeding Email Primitive demo accounts "
        f"(apply={args.apply})…\n"
    )
    summary = seed(apply=args.apply)
    print("\n── Summary ───────────────────────────────────────────")
    print(f"  Tenants seeded:    {summary['tenants_seeded']}")
    print(f"  Accounts created:  {summary['accounts_created']}")
    print(f"  Accounts skipped:  {summary['accounts_skipped']}")
    print(f"  Tenants missing:   {summary['tenants_missing']}")
    print(
        f"\n{'COMMITTED.' if args.apply else 'Dry run — pass --apply to commit.'}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
