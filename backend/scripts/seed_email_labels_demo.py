"""Seed sample email labels for the demo tenants —
Phase W-4b Layer 1 Step 4b.

Adds canonical labels (Priority / Customer / Internal / Vendor) to
the Sunnycrest tenant + Hopkins tenant (when seeded). Idempotent —
skips labels that already exist by name on the target tenant.

Demo accent palette aligned with DESIGN_LANGUAGE Aesthetic Arc Session 2:
  - Priority  → terracotta (single-value cross-mode accent)
  - Customer  → sage
  - Internal  → dusk lavender
  - Vendor    → muted brown

Usage (from backend/):
    DATABASE_URL=postgresql://localhost:5432/bridgeable_dev \\
        python -m scripts.seed_email_labels_demo            # dry-run
    DATABASE_URL=postgresql://localhost:5432/bridgeable_dev \\
        python -m scripts.seed_email_labels_demo --apply
"""

from __future__ import annotations

import argparse
import os
import sys


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, BACKEND_DIR)


from app.database import SessionLocal  # noqa: E402
from app.models.company import Company  # noqa: E402
from app.models.email_primitive import EmailLabel  # noqa: E402
from app.services.email import inbox_service  # noqa: E402


_LABEL_DEFAULTS = [
    {"name": "Priority", "color": "#9C5640"},  # terracotta
    {"name": "Customer", "color": "#4D7C5A"},  # sage
    {"name": "Internal", "color": "#5C5C8E"},  # dusk lavender
    {"name": "Vendor", "color": "#7C5040"},  # muted brown
]


def seed(*, apply: bool) -> dict:
    summary = {
        "tenants_seen": 0,
        "labels_created": 0,
        "labels_skipped": 0,
        "tenants_missing_admin": 0,
    }
    db = SessionLocal()
    try:
        for slug in ("testco", "hopkins-fh"):
            tenant = db.query(Company).filter(Company.slug == slug).first()
            if not tenant:
                print(f"  [skip] Tenant {slug!r} not found.")
                continue
            summary["tenants_seen"] += 1

            # Find any active user in tenant to be actor; if none,
            # skip (label creation needs an actor for audit log).
            from app.models.user import User

            admin = (
                db.query(User)
                .filter(
                    User.company_id == tenant.id,
                    User.is_active.is_(True),
                )
                .first()
            )
            if not admin:
                print(f"  [skip] Tenant {slug!r} has no active users.")
                summary["tenants_missing_admin"] += 1
                continue

            print(f"\nTenant '{slug}':")
            for spec in _LABEL_DEFAULTS:
                existing = (
                    db.query(EmailLabel)
                    .filter(
                        EmailLabel.tenant_id == tenant.id,
                        EmailLabel.name == spec["name"],
                    )
                    .first()
                )
                if existing:
                    print(f"  [skip] '{spec['name']}' already exists")
                    summary["labels_skipped"] += 1
                    continue
                if not apply:
                    print(
                        f"  [dry-run] Would create '{spec['name']}' "
                        f"({spec['color']})"
                    )
                    summary["labels_created"] += 1
                    continue
                label = inbox_service.create_label(
                    db,
                    tenant_id=tenant.id,
                    user_id=admin.id,
                    name=spec["name"],
                    color=spec["color"],
                )
                print(f"  [created] {label.name} ({label.color}) {label.id[:8]}")
                summary["labels_created"] += 1
        if apply:
            db.commit()
        else:
            db.rollback()
    finally:
        db.close()
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if not os.environ.get("DATABASE_URL"):
        print("ERROR: DATABASE_URL required.", file=sys.stderr)
        return 1
    if os.environ.get("ENVIRONMENT") == "production":
        print(
            "ERROR: refusing to run demo seed against production.",
            file=sys.stderr,
        )
        return 2

    print(f"Seeding email labels (apply={args.apply})…")
    summary = seed(apply=args.apply)
    print("\n── Summary ─────────────────────────────")
    print(f"  Tenants seen:    {summary['tenants_seen']}")
    print(f"  Labels created:  {summary['labels_created']}")
    print(f"  Labels skipped:  {summary['labels_skipped']}")
    print(
        f"\n{'COMMITTED.' if args.apply else 'Dry run — pass --apply to commit.'}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
