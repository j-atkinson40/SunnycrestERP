"""Seed the September 2026 demo scenario for FH-1b.

Creates:
  - Hopkins Funeral Home (funeral_home tenant) with admin + director users
  - St. Mary's Cemetery (cemetery tenant) with 40 seeded plots + map config
  - Active connections (Hopkins ↔ Sunnycrest, Hopkins ↔ St. Mary's)
  - Demo case FC-2026-0001: John Michael Smith, veteran, at the Story step
    with all merchandise selected, narrative pre-compiled, plot pre-selected.

Usage (from backend/):
    python -m scripts.seed_fh_demo              # dry-run summary
    python -m scripts.seed_fh_demo --apply      # actually apply

Refuses if ENVIRONMENT=production. Idempotent via slug checks.
"""

import argparse
import os
import secrets
import sys
import uuid
from datetime import date, datetime, time, timezone

from cryptography.fernet import Fernet
from sqlalchemy import text as sql_text

# Ensure encryption key is set before any crypto usage
os.environ.setdefault("BRIDGEABLE_ENCRYPTION_KEY", Fernet.generate_key().decode())

from app.core.security import hash_password  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models.cemetery_plot import CemeteryMapConfig, CemeteryPlot  # noqa: E402
from app.models.company import Company  # noqa: E402
from app.models.funeral_case import (  # noqa: E402
    CaseDeceased,
    CaseDisposition,
    CaseInformant,
    CaseMerchandise,
    CaseService as FHCaseService,
    CaseVeteran,
    FuneralCase,
)
from app.models.user import User  # noqa: E402
from app.services.fh import case_service, story_thread_service  # noqa: E402


def _ensure_company(db, slug, defaults) -> Company:
    c = db.query(Company).filter(Company.slug == slug).first()
    if c:
        return c
    c = Company(id=str(uuid.uuid4()), slug=slug, is_active=True, **defaults)
    db.add(c)
    db.commit()
    return c


def _ensure_user(db, company_id, email, defaults) -> User:
    u = db.query(User).filter(User.email == email).first()
    if u:
        return u
    u = User(
        id=str(uuid.uuid4()),
        company_id=company_id,
        email=email,
        is_active=True,
        hashed_password=hash_password(defaults.pop("password", "demo123")),
        **defaults,
    )
    db.add(u)
    db.commit()
    return u


def _ensure_relationship(db, tenant_id, supplier_id, rel_type):
    row = db.execute(
        sql_text(
            "SELECT id FROM platform_tenant_relationships "
            "WHERE tenant_id = :t AND supplier_tenant_id = :s"
        ),
        {"t": tenant_id, "s": supplier_id},
    ).fetchone()
    if row:
        return row[0]
    new_id = str(uuid.uuid4())
    db.execute(
        sql_text(
            "INSERT INTO platform_tenant_relationships "
            "(id, tenant_id, supplier_tenant_id, relationship_type, status, connected_at, created_at) "
            "VALUES (:id, :t, :s, :r, 'active', now(), now())"
        ),
        {"id": new_id, "t": tenant_id, "s": supplier_id, "r": rel_type},
    )
    db.commit()
    return new_id


def _seed_plots(db, cemetery_id, force: bool):
    existing = db.query(CemeteryPlot).filter(CemeteryPlot.company_id == cemetery_id).count()
    if existing > 0 and not force:
        return existing
    # 40 plots in 4 sections (A–D), 5 rows × 2 plots per row
    sections = ["A", "B", "C", "D"]
    count = 0
    # Grid layout — each section occupies a 48×24 box inside the 100×100 viewBox
    # Section positions: A=(2,2) B=(52,2) C=(2,52) D=(52,52)
    section_origin = {"A": (2, 2), "B": (52, 2), "C": (2, 52), "D": (52, 52)}
    for sec in sections:
        ox, oy = section_origin[sec]
        for r in range(1, 6):
            for n in range(1, 9):
                x = ox + (n - 1) * 5.5
                y = oy + (r - 1) * 4.2
                # Plot A-4-12 is the demo pre-selected plot — give it special attributes
                is_hero = sec == "A" and r == 4 and n == 1
                plot = CemeteryPlot(
                    id=str(uuid.uuid4()),
                    company_id=cemetery_id,
                    section=sec,
                    row=str(r),
                    number=str(n),
                    plot_label=f"{sec}-{r}-{n}",
                    plot_type="double" if is_hero else "single",
                    status="available",
                    map_x=x,
                    map_y=y,
                    map_width=4.8,
                    map_height=3.7,
                    price=2400 if is_hero else 1800 + (ord(sec) - ord("A")) * 100,
                    opening_closing_fee=850,
                )
                db.add(plot)
                count += 1

    # Map config
    existing_cfg = db.query(CemeteryMapConfig).filter(CemeteryMapConfig.company_id == cemetery_id).first()
    if not existing_cfg:
        cfg = CemeteryMapConfig(
            id=str(uuid.uuid4()),
            company_id=cemetery_id,
            map_width_ft=480,
            map_height_ft=480,
            sections=[
                {"name": "A", "color": "#f0f9ff", "description": "Section A — Main lawn"},
                {"name": "B", "color": "#fef3c7", "description": "Section B — Garden"},
                {"name": "C", "color": "#e0e7ff", "description": "Section C — Oaks"},
                {"name": "D", "color": "#fce7f3", "description": "Section D — Veterans"},
            ],
            legend=[
                {"plot_type": "single", "color": "#4ade80", "label": "Available"},
                {"plot_type": "double", "color": "#60a5fa", "label": "Companion"},
            ],
        )
        db.add(cfg)

    db.commit()
    return count


def _seed_demo_case(db, hopkins_id, director_id, mfr_id, cemetery_id, force: bool):
    existing = db.query(FuneralCase).filter(
        FuneralCase.company_id == hopkins_id,
        FuneralCase.case_number.like("FC-%-0001"),
    ).first()
    if existing and not force:
        return existing

    if existing:
        # Clean slate
        db.execute(sql_text("DELETE FROM funeral_case_notes WHERE case_id = :c"), {"c": existing.id})
        db.execute(sql_text("DELETE FROM case_merchandise WHERE case_id = :c"), {"c": existing.id})
        db.execute(sql_text("DELETE FROM case_informants WHERE case_id = :c"), {"c": existing.id})
        db.execute(sql_text("DELETE FROM case_deceased WHERE case_id = :c"), {"c": existing.id})
        db.execute(sql_text("DELETE FROM case_service WHERE case_id = :c"), {"c": existing.id})
        db.execute(sql_text("DELETE FROM case_disposition WHERE case_id = :c"), {"c": existing.id})
        db.execute(sql_text("DELETE FROM case_cemetery WHERE case_id = :c"), {"c": existing.id})
        db.execute(sql_text("DELETE FROM case_cremation WHERE case_id = :c"), {"c": existing.id})
        db.execute(sql_text("DELETE FROM case_veteran WHERE case_id = :c"), {"c": existing.id})
        db.execute(sql_text("DELETE FROM case_financials WHERE case_id = :c"), {"c": existing.id})
        db.execute(sql_text("DELETE FROM case_preneed WHERE case_id = :c"), {"c": existing.id})
        db.execute(sql_text("DELETE FROM case_aftercare WHERE case_id = :c"), {"c": existing.id})
        db.execute(sql_text("DELETE FROM case_vaults WHERE case_id = :c"), {"c": existing.id})
        db.delete(existing)
        db.commit()

    # Create case + satellites
    case = case_service.create_case(db, hopkins_id, director_id=director_id)
    # Override case_number to FC-2026-0001 for demo consistency
    case.case_number = "FC-2026-0001"
    case.vault_manufacturer_company_id = mfr_id
    case.cemetery_company_id = cemetery_id
    case.current_step = "story"
    case.completed_steps = [
        "arrangement_conference",
        "vital_statistics",
        "authorization",
        "service_planning",
        "obituary",
        "merchandise_vault",
        "merchandise_casket",
        "merchandise_monument",
    ]
    db.commit()

    # Deceased — John Michael Smith
    dec = db.query(CaseDeceased).filter(CaseDeceased.case_id == case.id).first()
    dec.first_name = "John"
    dec.middle_name = "Michael"
    dec.last_name = "Smith"
    dec.date_of_birth = date(1942, 3, 3)
    dec.date_of_death = date(2026, 4, 9)
    dec.sex = "male"
    dec.religion = "Catholic"
    dec.occupation = "Steelworker (retired)"
    dec.marital_status = "married"
    dec.place_of_death_name = "Hopkins Memorial Hospital"
    dec.residence_city = "Syracuse"
    dec.residence_state = "NY"
    dec.spouse_name = "Mary Smith"

    # Veteran
    vet = db.query(CaseVeteran).filter(CaseVeteran.case_id == case.id).first()
    vet.ever_in_armed_forces = True
    vet.branch = "US Army"
    vet.service_start_date = date(1962, 6, 1)
    vet.service_end_date = date(1965, 8, 15)
    vet.dd214_on_file = True
    vet.va_flag_requested = True

    # Disposition
    disp = db.query(CaseDisposition).filter(CaseDisposition.case_id == case.id).first()
    disp.disposition_type = "burial"
    disp.death_certificate_status = "pending"

    # Service
    svc = db.query(FHCaseService).filter(FHCaseService.case_id == case.id).first()
    svc.service_type = "church"
    svc.service_date = date(2026, 4, 13)
    svc.service_time = time(14, 0)
    svc.service_location_name = "First Baptist Church"
    svc.service_location_address = "123 Main St, Syracuse, NY"
    svc.officiant_name = "Fr. Thomas Burke"

    # Informant — Mary Smith (primary + authorizing, signed)
    db.add(CaseInformant(
        id=str(uuid.uuid4()),
        case_id=case.id,
        company_id=hopkins_id,
        name="Mary Smith",
        relationship="spouse",
        phone="555-0142",
        is_primary=True,
        is_authorizing=True,
        authorization_signed_at=datetime.now(timezone.utc),
        authorization_method="in_person",
    ))

    # Merchandise — vault, casket, monument
    merch = db.query(CaseMerchandise).filter(CaseMerchandise.case_id == case.id).first()
    merch.vault_product_name = "Monticello Standard"
    merch.vault_price = 1850
    merch.vault_personalization = {
        "emblem_key": "american_flag",
        "name_display": "JOHN M. SMITH",
        "font": "Heritage",
        "birth_date_display": "March 3, 1942",
        "death_date_display": "April 9, 2026",
    }
    merch.vault_approved_at = datetime.now(timezone.utc)
    merch.casket_product_name = "Mahogany Heritage"
    merch.casket_price = 3450
    merch.casket_personalization = {"interior": "Cream crepe"}
    merch.casket_approved_at = datetime.now(timezone.utc)
    merch.monument_shape = "upright_standard"
    merch.monument_stone = "absolute_black"
    merch.monument_name_text = "SMITH"
    merch.monument_dates_text = "1942 — 2026"
    merch.monument_engraving_key = "army"
    merch.monument_inscription = "Beloved Husband and Father"
    merch.monument_approved_at = datetime.now(timezone.utc)

    # Pre-select plot A-4-1 as the demo plot (the hero double plot)
    from app.models.funeral_case import CaseCemetery
    hero_plot = (
        db.query(CemeteryPlot)
        .filter(CemeteryPlot.company_id == cemetery_id, CemeteryPlot.section == "A", CemeteryPlot.row == "4", CemeteryPlot.number == "1")
        .first()
    )
    if hero_plot:
        cem = db.query(CaseCemetery).filter(CaseCemetery.case_id == case.id).first()
        cem.cemetery_name = "St. Mary's Cemetery"
        cem.cemetery_address = "200 Cemetery Rd, Syracuse, NY"
        cem.section = hero_plot.section
        cem.row = hero_plot.row
        cem.plot_number = hero_plot.number
        cem.plot_id = hero_plot.id
        # Leave plot status as 'available' — demo director will click Approve All
        # to flip it to 'sold' via the real flow.

    db.commit()
    db.refresh(case)

    # Pre-compile narrative
    try:
        story_thread_service.compile_narrative(db, case.id)
    except Exception:
        case.story_thread_narrative = (
            "John will be honored at First Baptist Church with military honors reflecting his "
            "service in the US Army, a Catholic ceremony befitting his lifelong faith, and an "
            "Army-engraved monument at St. Mary's marking a life of quiet strength and devotion "
            "to his family."
        )
        case.story_thread_status = "ready"
        case.story_thread_compiled_at = datetime.now(timezone.utc)
        db.commit()

    return case


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Actually apply changes (default: dry-run)")
    parser.add_argument("--force", action="store_true", help="Recreate the demo case even if one exists")
    args = parser.parse_args()

    if os.getenv("ENVIRONMENT", "").lower() == "production":
        print("SAFETY: Refusing to run in production.")
        sys.exit(2)

    if not args.apply:
        print("DRY-RUN — pass --apply to execute.")
        print("Would create/ensure:")
        print("  - hopkinsfh tenant + admin + 2 directors + office")
        print("  - stmarys cemetery tenant + admin")
        print("  - 40 plots in 4 sections with map config")
        print("  - platform_tenant_relationships: hopkinsfh → sunnycrest (manufacturer)")
        print("  - platform_tenant_relationships: hopkinsfh → stmarys (cemetery)")
        print("  - Demo case FC-2026-0001 (John Michael Smith) at the Story step")
        return

    db = SessionLocal()
    try:
        # Hopkins FH
        hopkins = _ensure_company(db, "hopkinsfh", {
            "name": "Hopkins Funeral Home",
            "vertical": "funeral_home",
        })
        admin = _ensure_user(db, hopkins.id, "admin@hopkinsfh.test", {
            "first_name": "James",
            "last_name": "Hopkins",
            "role": "admin",
            "password": "DemoAdmin123!",
        })
        torres = _ensure_user(db, hopkins.id, "director1@hopkinsfh.test", {
            "first_name": "Michael",
            "last_name": "Torres",
            "role": "director",
            "password": "DemoDirector123!",
        })
        chen = _ensure_user(db, hopkins.id, "director2@hopkinsfh.test", {
            "first_name": "Sarah",
            "last_name": "Chen",
            "role": "director",
            "password": "DemoDirector123!",
        })
        _ensure_user(db, hopkins.id, "office@hopkinsfh.test", {
            "first_name": "Lisa",
            "last_name": "Johnson",
            "role": "office",
            "password": "DemoOffice123!",
        })

        # St Mary's Cemetery
        stmarys = _ensure_company(db, "stmarys", {
            "name": "St. Mary's Cemetery",
            "vertical": "cemetery",
        })
        _ensure_user(db, stmarys.id, "admin@stmarys.test", {
            "first_name": "Cemetery",
            "last_name": "Admin",
            "role": "admin",
            "password": "DemoCemetery123!",
        })

        # Sunnycrest (assumed to exist)
        sunnycrest = db.query(Company).filter(Company.slug == "sunnycrest").first()

        # Relationships
        if sunnycrest:
            _ensure_relationship(db, hopkins.id, sunnycrest.id, "fh_manufacturer")
            print(f"  ✓ Relationship: Hopkins → Sunnycrest (manufacturer)")
        else:
            print(f"  ⚠ Sunnycrest tenant not found — vault cross-tenant connection skipped")
        _ensure_relationship(db, hopkins.id, stmarys.id, "fh_cemetery")
        print(f"  ✓ Relationship: Hopkins → St. Mary's (cemetery)")

        # Plots
        n_plots = _seed_plots(db, stmarys.id, force=args.force)
        print(f"  ✓ Plots seeded: {n_plots}")

        # Demo case
        case = _seed_demo_case(db, hopkins.id, torres.id, sunnycrest.id if sunnycrest else None, stmarys.id, force=args.force)
        print(f"  ✓ Demo case: {case.case_number} (id={case.id}, step={case.current_step})")

        print("\n✓ Demo scenario seeded.")
        print(f"  Login: admin@hopkinsfh.test / DemoAdmin123!")
        print(f"  Director: director1@hopkinsfh.test / DemoDirector123!")
        print(f"  Open {case.case_number} and click 'Continue: The Story →' to demo the Approve All flow.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
