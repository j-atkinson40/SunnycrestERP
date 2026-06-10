"""Seed the JCF cross-tenant demo relationship (staging).

Ensures an ACTIVE PlatformTenantRelationship between the canonical dev
tenants hopkins-fh (funeral_home) and testco (manufacturing) so the JCF
flow — vault order landing at the manufacturer, FocusShare grant across
the relationship — runs on staging per the testing framework. Gracefully
skips when either tenant is absent (mirrors seed_fh_demo's
sunnycrest-skip discipline).

DEMO CONTENT: refuses to run in production (the canonical seed runner
runs everywhere; this guard is the seed's own responsibility).

Usage:
    cd backend && python -m scripts.seed_jcf_demo
"""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.database import SessionLocal  # noqa: E402
from app.models.company import Company  # noqa: E402
from app.models.platform_tenant_relationship import (  # noqa: E402
    PlatformTenantRelationship,
)


def seed(db) -> str:
    fh = db.query(Company).filter(Company.slug == "hopkins-fh").first()
    mfr = db.query(Company).filter(Company.slug == "testco").first()
    if fh is None or mfr is None:
        return "skipped (hopkins-fh or testco absent)"

    existing = (
        db.query(PlatformTenantRelationship)
        .filter(
            PlatformTenantRelationship.tenant_id.in_([fh.id, mfr.id]),
            PlatformTenantRelationship.supplier_tenant_id.in_([fh.id, mfr.id]),
        )
        .first()
    )
    if existing is not None:
        if existing.status != "active":
            existing.status = "active"
            db.commit()
            return "reactivated"
        return "noop"

    rel = PlatformTenantRelationship(
        id=str(uuid.uuid4()),
        tenant_id=fh.id,
        supplier_tenant_id=mfr.id,
        relationship_type="supplier",
        status="active",
    )
    db.add(rel)
    db.commit()
    return "created"


def main() -> None:
    if os.environ.get("ENVIRONMENT", "dev") == "production":
        print("[seed_jcf_demo] ENVIRONMENT=production — refusing to seed demo content.")
        return
    db = SessionLocal()
    try:
        print(f"[seed_jcf_demo] {seed(db)}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
