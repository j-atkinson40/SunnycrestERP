"""Phase 4 demo data seed — companies + cases for NL overlay staging.

Seeds into a named tenant so the Wilbert-demo flow has real vault
rows to fuzzy-match against:

  Hopkins Funeral Home    — CompanyEntity (is_funeral_home=True)
  Riverside Funeral Home  — CompanyEntity (is_funeral_home=True)
  Whitney Funeral Home    — CompanyEntity (is_funeral_home=True)
  Oakwood Memorial        — CompanyEntity (is_cemetery=True)
  Acme Manufacturing      — CompanyEntity (is_customer=True) [mfg demo]

Plus 3 FHCase rows (Hopkins-family, Smith-family, Taylor-family) so
the fh_case resolver has something to hit during demo runs.

Idempotent — looks up by slug+name before inserting. Safe to re-run
on staging between demos.

Run:
    cd backend && source .venv/bin/activate
    DATABASE_URL=<staging-url> python scripts/seed_nl_demo_data.py \\
        --tenant-slug testco

If --tenant-slug is omitted, defaults to "testco" (the staging
canonical tenant). Fails loudly if the tenant doesn't exist.

Documents what rows the demo depends on so regressions are
re-seedable in a single command.
"""

from __future__ import annotations

import argparse
import sys
import uuid
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.company import Company
from app.models.company_entity import CompanyEntity
from app.models.funeral_case import (
    CaseDeceased,
    CaseInformant,
    CaseService,
    FuneralCase,
)


# ── Demo row definitions ────────────────────────────────────────────


_COMPANY_ENTITIES: list[dict] = [
    {
        "name": "Hopkins Funeral Home",
        "flags": {"is_funeral_home": True},
    },
    {
        "name": "Riverside Funeral Home",
        "flags": {"is_funeral_home": True},
    },
    {
        "name": "Whitney Funeral Home",
        "flags": {"is_funeral_home": True},
    },
    {
        "name": "Oakwood Memorial",
        "flags": {"is_cemetery": True},
    },
    {
        "name": "St. Mary's Church",
        "flags": {"is_cemetery": False},  # service location use case
    },
    {
        "name": "Acme Manufacturing",
        "flags": {"is_customer": True},
    },
]


# 3 prior FH cases so the case resolver has realistic data. Names
# are generic family names unlikely to collide with demo input.
_PRIOR_CASES: list[dict] = [
    {
        "deceased_first_name": "Eleanor",
        "deceased_last_name": "Andersen",
        "days_ago_dod": 45,
        "service_days_ago": 40,
    },
    {
        "deceased_first_name": "Harold",
        "deceased_last_name": "Martinez",
        "days_ago_dod": 30,
        "service_days_ago": 25,
    },
    {
        "deceased_first_name": "Grace",
        "deceased_last_name": "Nakamura",
        "days_ago_dod": 14,
        "service_days_ago": 10,
    },
]


# ── Seeder ──────────────────────────────────────────────────────────


def seed_for_tenant(db: Session, tenant_slug: str) -> dict[str, int]:
    company = (
        db.query(Company).filter(Company.slug == tenant_slug).first()
    )
    if company is None:
        raise SystemExit(
            f"Tenant with slug {tenant_slug!r} not found. "
            "Create the tenant first (staging bootstrap script)."
        )

    stats = {"company_entities_added": 0, "cases_added": 0}

    # ── CompanyEntities ────────────────────────────────────────
    for spec in _COMPANY_ENTITIES:
        existing = (
            db.query(CompanyEntity)
            .filter(
                CompanyEntity.company_id == company.id,
                CompanyEntity.name == spec["name"],
            )
            .first()
        )
        if existing is not None:
            continue
        ent = CompanyEntity(
            id=str(uuid.uuid4()),
            company_id=company.id,
            name=spec["name"],
            is_active=True,
            **spec["flags"],
        )
        db.add(ent)
        stats["company_entities_added"] += 1
    db.commit()

    # ── FH cases (only for funeral_home vertical) ──────────────
    if company.vertical == "funeral_home":
        for idx, case_spec in enumerate(_PRIOR_CASES):
            case_number = f"DEMO-{idx:04d}"
            existing = (
                db.query(FuneralCase)
                .filter(
                    FuneralCase.company_id == company.id,
                    FuneralCase.case_number == case_number,
                )
                .first()
            )
            if existing is not None:
                continue

            case = FuneralCase(
                id=str(uuid.uuid4()),
                company_id=company.id,
                case_number=case_number,
                status="active",
                current_step="arrangement_conference",
                completed_steps=[],
                story_thread_status="building",
            )
            db.add(case)
            db.flush()

            # Satellites
            today = date.today()
            dod = today - timedelta(days=case_spec["days_ago_dod"])
            service_date = today - timedelta(days=case_spec["service_days_ago"])

            db.add(
                CaseDeceased(
                    id=str(uuid.uuid4()),
                    case_id=case.id,
                    company_id=company.id,
                    first_name=case_spec["deceased_first_name"],
                    last_name=case_spec["deceased_last_name"],
                    date_of_death=dod,
                )
            )
            db.add(
                CaseService(
                    id=str(uuid.uuid4()),
                    case_id=case.id,
                    company_id=company.id,
                    service_date=service_date,
                    service_type="funeral",
                )
            )
            db.add(
                CaseInformant(
                    id=str(uuid.uuid4()),
                    case_id=case.id,
                    company_id=company.id,
                    name=f"{case_spec['deceased_first_name']} {case_spec['deceased_last_name']} family",
                    relationship="family",
                    is_primary=True,
                )
            )
            stats["cases_added"] += 1
        db.commit()

    return stats


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--tenant-slug",
        default="testco",
        help="Target tenant slug (default: testco).",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        stats = seed_for_tenant(db, args.tenant_slug)
        print(f"[nl-demo-seed] tenant={args.tenant_slug} stats={stats}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
