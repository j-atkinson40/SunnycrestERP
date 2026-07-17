"""Sunnycrest activated (The Sunnycrest Workshop, commit set 1).

The OPERATOR'S REAL COMPANY as the manufacturing development tenant — not
demo fluff. This seed is deliberately different in kind from seed_staging
(clean+reseed) and seed_fh_demo (demo content):

  STRICTLY ENSURE-ONLY, PRESERVE-AWARE. It creates what's MISSING and
  touches NOTHING that exists. The tenant's CONTENT is the operator's to
  author — that's the whole point — and his authored work must survive
  every future boot. Concretely:
    - company row exists → left byte-untouched (name, settings, everything);
    - his admin user exists → left byte-untouched (password included);
    - a module row exists → its enabled flag is HIS (never re-enabled);
    - only genuinely-missing rows are created.

  On staging the company + operator admin already exist (created by hand) —
  this seed adopts them as-is and only backfills gaps (role catalog,
  missing module rows). On a fresh dev DB it creates the tenant whole.

TEMP PASSWORD DISCIPLINE: when the admin user must be CREATED (fresh dev),
its password is generated at runtime (secrets) and printed ONCE — never a
real credential in code. Override via SUNNYCREST_ADMIN_TEMP_PASSWORD for
dev convenience. The operator rotates on first login.

The merged Bridgeable Map populates itself from the manufacturing
vertical_default catalog — no per-tenant map seeding needed (and none
wanted: his map content is his to author).

Idempotent; exit 0 either way. Refuses on ENVIRONMENT=production.
"""
from __future__ import annotations

import os
import secrets
import sys
import uuid
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.security import hash_password  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models.company import Company  # noqa: E402
from app.models.role import Role  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services.role_service import seed_default_roles  # noqa: E402
from sqlalchemy import text as sql_text  # noqa: E402

SLUG = "sunnycrest"
NAME = "Sunnycrest Precast"
ADMIN_EMAIL = "jim.atkinson@sunnycrest.com"
MODULES = [
    "sales", "products", "inventory", "driver_delivery", "purchasing",
    "safety", "hr_time", "pos",
]


def main() -> int:
    if os.environ.get("ENVIRONMENT") == "production":
        print("[seed_sunnycrest] ENVIRONMENT=production — refusing.")
        return 1

    db = SessionLocal()
    created: list[str] = []
    try:
        company = db.query(Company).filter(Company.slug == SLUG).first()
        if company is None:
            company = Company(
                id=str(uuid.uuid4()), slug=SLUG, name=NAME,
                vertical="manufacturing", is_active=True,
                timezone="America/New_York",
            )
            db.add(company)
            db.commit()
            created.append("company")

        # Role catalog — seed_default_roles is idempotent (no-op when present).
        seed_default_roles(db, company.id)
        db.commit()

        admin = (
            db.query(User)
            .filter(User.company_id == company.id, User.email == ADMIN_EMAIL)
            .first()
        )
        if admin is None:
            role = (
                db.query(Role)
                .filter(Role.company_id == company.id, Role.slug == "admin")
                .first()
            )
            if role is None:
                raise RuntimeError(
                    "admin role missing after seed_default_roles — refusing "
                    "to create a role-less user"
                )
            temp_password = os.environ.get(
                "SUNNYCREST_ADMIN_TEMP_PASSWORD"
            ) or secrets.token_urlsafe(12)
            admin = User(
                id=str(uuid.uuid4()), company_id=company.id, email=ADMIN_EMAIL,
                first_name="Jim", last_name="Atkinson",
                hashed_password=hash_password(temp_password),
                role_id=role.id, is_active=True,
            )
            db.add(admin)
            db.commit()
            created.append("admin_user")
            # Printed ONCE, at creation, never stored — rotate on first login.
            print(f"[seed_sunnycrest] TEMP admin password for {ADMIN_EMAIL}: "
                  f"{temp_password}  (rotate on first login)")

        # Modules: create-if-missing ONLY. An existing row's enabled flag is
        # the operator's — a deliberately-disabled module must stay disabled.
        now = datetime.now(timezone.utc)
        for mod in MODULES:
            exists = db.execute(
                sql_text(
                    "SELECT 1 FROM company_modules WHERE company_id = :cid "
                    "AND module = :mod"
                ),
                {"cid": company.id, "mod": mod},
            ).first()
            if exists is None:
                db.execute(
                    sql_text(
                        "INSERT INTO company_modules (id, company_id, module, "
                        "enabled, created_at, updated_at) VALUES "
                        "(:id, :cid, :mod, true, :now, :now)"
                    ),
                    {"id": str(uuid.uuid4()), "cid": company.id, "mod": mod,
                     "now": now},
                )
                created.append(f"module:{mod}")
        db.commit()

        print(f"[seed_sunnycrest] ok — company={company.id} "
              f"created={created or 'nothing (all present, untouched)'}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
