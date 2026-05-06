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
from app.models.role import Role  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services.fh import case_service, story_thread_service  # noqa: E402
from app.services.role_service import seed_default_roles  # noqa: E402

# Phase 1G — Personalization Studio canonical demo seed integration.
# Imports deferred to call sites to keep module-load latency low at
# the existing seed shape; these are referenced only inside
# `_seed_personalization_studio_phase1g`.
import json  # noqa: E402  # canonical-restraint: small set of imports


def _ensure_company(db, slug, defaults) -> Company:
    c = db.query(Company).filter(Company.slug == slug).first()
    if c:
        # R-1.6.3: ensure tenant role catalog exists even on existing
        # Hopkins rows pre-dating the seed fix. Idempotent — no-op
        # if the catalog is already present.
        seed_default_roles(db, c.id)
        return c
    c = Company(id=str(uuid.uuid4()), slug=slug, is_active=True, **defaults)
    db.add(c)
    db.commit()
    # R-1.6.3: Hopkins-tenant default role catalog. Pre-R-1.6.3 the
    # seed never called this; users couldn't be created (TypeError on
    # `User(role="admin", ...)`) AND impersonation couldn't find an
    # admin user even if creation had worked. Both pre-conditions
    # are repaired by seeding canonical tenant roles here.
    seed_default_roles(db, c.id)
    return c


def _ensure_user(db, company_id, email, defaults) -> User:
    u = db.query(User).filter(User.email == email).first()
    if u:
        return u

    # R-1.6.3: Pre-R-1.6.3 the seed passed `role` (string) into
    # `User(**defaults)`. The User model has `role_id` (UUID FK to
    # roles, NOT NULL) — `role` is not a mapped attribute. SQLAlchemy
    # raised TypeError on every `_ensure_user` call after the first
    # `_ensure_company` commit, leaving Hopkins partially seeded
    # (company exists, no users). Six R-* phases shipped on this
    # broken state because railway-start.sh swallowed the error
    # (also fixed in this patch — Part 2).
    #
    # Fix: pop the role slug from defaults, resolve it to a real
    # Role row scoped to this tenant, pass `role_id=role.id` to the
    # User constructor.
    role_slug = defaults.pop("role", "employee")
    role = (
        db.query(Role)
        .filter(
            Role.company_id == company_id,
            Role.slug == role_slug,
            Role.is_system == True,
        )
        .first()
    )
    if role is None:
        # Explicit failure — silent fallback to None role_id would
        # make the same bug return (FK violation at flush time, but
        # harder to diagnose than this loud error here).
        raise RuntimeError(
            f"Role {role_slug!r} not found for company {company_id}. "
            "Did seed_default_roles run on _ensure_company? "
            "_ensure_company is responsible for tenant role-catalog "
            "seeding before any _ensure_user calls."
        )

    u = User(
        id=str(uuid.uuid4()),
        company_id=company_id,
        email=email,
        is_active=True,
        hashed_password=hash_password(defaults.pop("password", "demo123")),
        role_id=role.id,
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


# ─────────────────────────────────────────────────────────────────────
# Phase 1G — Personalization Studio canonical demo seed integration
#
# Per Phase 1G build prompt + §3.26.11.12.19.1 canonical demo seed
# scope: extends canonical Hopkins FH + Sunnycrest demo with canonical
# Personalization Studio Generation Focus instance + canvas state +
# Workshop catalog overrides + Q1 display label overrides + pre-shared
# Hopkins→Sunnycrest DocumentShare.
#
# Idempotent canonical seed pattern — fresh→create + matched→noop +
# differing→update + multiple→skip-with-warning per Sessions 1-7
# precedent.
# ─────────────────────────────────────────────────────────────────────


# Hopkins canonical per-tenant Workshop catalog override (canonical
# subset of canonical-default catalogs per Tune mode boundary).
_HOPKINS_FONT_CATALOG = ["serif", "italic", "uppercase"]
_HOPKINS_EMBLEM_CATALOG = [
    "rose",
    "cross",
    "praying_hands",
    "dove",
    "wreath",
    "patriotic_flag",
]
_HOPKINS_LEGACY_PRINT_CATALOG: list[str] | None = None  # default — full catalog


# Sunnycrest canonical per-tenant Workshop catalog override + Q1
# canonical "Vinyl" display label override per r74 substrate.
_SUNNYCREST_FONT_CATALOG = ["serif", "sans"]
_SUNNYCREST_EMBLEM_CATALOG = [
    "rose",
    "cross",
    "praying_hands",
    "dove",
    "wreath",
    "patriotic_flag",
]


# Wilbert canonical Q1 display label override per r74 substrate
# (canonical "Life's Reflections" override on canonical ``vinyl`` option
# type). Surfaces only when Wilbert tenant exists in seed; otherwise
# documented for future Wilbert tenant onboarding.
_WILBERT_VINYL_DISPLAY_LABEL = "Life's Reflections"


# Canonical Personalization Studio canvas state pre-rendered at demo
# seed for FC-2026-0001 (canonical post-r74 4-options vocabulary).
def _hopkins_demo_canvas_state(case_id: str) -> dict:
    return {
        "schema_version": 1,
        "template_type": "burial_vault_personalization_studio",
        "canvas_layout": {
            "elements": [
                {
                    "id": str(uuid.uuid4()),
                    "element_type": "name_text",
                    "x": 100,
                    "y": 80,
                    "config": {
                        "name_display": "JOHN M. SMITH",
                        "font": "uppercase",
                    },
                },
                {
                    "id": str(uuid.uuid4()),
                    "element_type": "emblem",
                    "x": 100,
                    "y": 160,
                    "config": {"emblem_key": "patriotic_flag"},
                },
            ],
        },
        "vault_product": {
            "vault_product_id": None,
            "vault_product_name": "Monticello Standard",
        },
        "emblem_key": "patriotic_flag",
        "name_display": "JOHN M. SMITH",
        "font": "uppercase",
        "birth_date_display": "March 3, 1942",
        "death_date_display": "April 9, 2026",
        "nameplate_text": None,
        "options": {
            "legacy_print": None,
            "physical_nameplate": None,
            "physical_emblem": {},
            "vinyl": None,
        },
        "family_approval_status": "approved",
    }


def _seed_workshop_catalog_overrides(
    db,
    company,
    *,
    font_catalog: list[str] | None,
    emblem_catalog: list[str] | None,
    legacy_print_catalog: list[str] | None,
    display_labels_override: dict[str, str] | None,
    template_type: str = "burial_vault_personalization_studio",
):
    """Idempotent seed of per-tenant Workshop catalog overrides at
    ``Company.settings_json`` JSONB-as-Text substrate per Phase 1D canon.

    No-op skip when override values match existing tenant override.
    Update on differing values.

    Phase 2D substrate-consumption-follower extension: ``template_type``
    kwarg parameterizes the workshop sub-key. Phase 1G default value
    preserves backward compatibility with Step 1 callers.
    """
    raw = company.settings_json or "{}"
    try:
        settings = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        settings = {}

    workshop = settings.get("workshop") or {}
    if not isinstance(workshop, dict):
        workshop = {}
    template_node = workshop.get(template_type) or {}
    if not isinstance(template_node, dict):
        template_node = {}

    changed = False
    if font_catalog is not None and template_node.get("font_catalog") != font_catalog:
        template_node["font_catalog"] = font_catalog
        changed = True
    if (
        emblem_catalog is not None
        and template_node.get("emblem_catalog") != emblem_catalog
    ):
        template_node["emblem_catalog"] = emblem_catalog
        changed = True
    if (
        legacy_print_catalog is not None
        and template_node.get("legacy_print_catalog") != legacy_print_catalog
    ):
        template_node["legacy_print_catalog"] = legacy_print_catalog
        changed = True

    if changed:
        workshop[template_type] = template_node
        settings["workshop"] = workshop

    # Display labels live at top-level ``personalization_display_labels``
    # key per Q1 r74 substrate — shared across all template_types at
    # category scope per §3.26.11.12.19.6 scope freeze (per-template
    # display label override is canonically not yet a concept; Q1 canon
    # operates at category scope).
    if display_labels_override:
        existing_labels = settings.get("personalization_display_labels") or {}
        if not isinstance(existing_labels, dict):
            existing_labels = {}
        merged = {**existing_labels, **display_labels_override}
        if merged != existing_labels:
            settings["personalization_display_labels"] = merged
            changed = True

    if changed:
        company.settings_json = json.dumps(settings)
        db.flush()
    return changed


def _seed_personalization_studio_phase1g(db, hopkins, sunnycrest, case):
    """Phase 1G canonical demo seed integration.

    Creates / refreshes:
      1. Personalization Studio managed email templates (re-runs Phase 1E
         idempotent seed; canonical noop on second invocation)
      2. Hopkins per-tenant Workshop catalog overrides + Q1 display label
         resolution (canonical default — no override seeded for Hopkins)
      3. Sunnycrest per-tenant Workshop catalog overrides + Q1 "Vinyl"
         canonical-explicit override (canonical Sunnycrest-specific label
         per build prompt)
      4. Canonical Document at canonical D-9 substrate for FC-2026-0001
         (document_type="burial_vault_personalization_studio";
         entity_type="fh_case"; status="committed")
      5. Canonical Generation Focus instance at canonical Phase 1A entity
         model (lifecycle_state="committed";
         family_approval_status="approved"; canvas state pre-rendered to
         canonical Document substrate via canonical Phase 1A
         commit_canvas_state path)
      6. Canonical pre-shared DocumentShare Hopkins→Sunnycrest at
         canonical D-6 substrate (demonstrates canonical cross-tenant
         flow visibility; canonical seed entry at canonical
         document_shares table)

    Returns canonical summary dict for canonical seed-output stdout
    consumption.
    """
    summary: dict = {
        "email_templates": "skipped",
        "hopkins_workshop_overrides": "skipped",
        "sunnycrest_workshop_overrides": "skipped",
        "wilbert_q1_label": "absent",
        "ps_document": "skipped",
        "ps_instance": "skipped",
        "documentshare": "skipped",
    }

    # Step 1: canonical Phase 1E managed email templates idempotent
    # seed (canonical Sessions 1-7 idempotent state machine).
    try:
        from scripts.seed_personalization_studio_phase1e_email_templates import (
            seed_phase1e_email_templates,
        )

        counters = seed_phase1e_email_templates(db)
        # Counters dict surfaces canonical 4-state outcome per template:
        # created / noop_matched / platform_update / skipped_customized.
        any_created = any(
            c.get("created", 0) > 0 for c in counters.values()
        )
        any_updated = any(
            c.get("platform_update", 0) > 0 for c in counters.values()
        )
        if any_created:
            summary["email_templates"] = "created"
        elif any_updated:
            summary["email_templates"] = "updated"
        else:
            summary["email_templates"] = "noop_matched"
    except Exception as exc:  # noqa: BLE001 — best-effort seed
        summary["email_templates"] = f"failed: {type(exc).__name__}"

    # Step 2: Hopkins per-tenant Workshop overrides (Hopkins selects
    # canonical default Q1 label "Vinyl"; canonical Hopkins-specific
    # canonical font + emblem subset overrides applied).
    if _seed_workshop_catalog_overrides(
        db,
        hopkins,
        font_catalog=_HOPKINS_FONT_CATALOG,
        emblem_catalog=_HOPKINS_EMBLEM_CATALOG,
        legacy_print_catalog=_HOPKINS_LEGACY_PRINT_CATALOG,
        display_labels_override=None,
    ):
        summary["hopkins_workshop_overrides"] = "applied"
    else:
        summary["hopkins_workshop_overrides"] = "noop_matched"

    # Step 3: Sunnycrest per-tenant Workshop overrides + canonical Q1
    # "Vinyl" canonical-explicit override.
    if sunnycrest is not None:
        # Refresh canonical Sunnycrest object from canonical session for
        # canonical settings_json mutation (canonical demo-seed
        # canonical session-fresh instance).
        sunnycrest_fresh = (
            db.query(Company).filter(Company.id == sunnycrest.id).first()
        )
        if _seed_workshop_catalog_overrides(
            db,
            sunnycrest_fresh,
            font_catalog=_SUNNYCREST_FONT_CATALOG,
            emblem_catalog=_SUNNYCREST_EMBLEM_CATALOG,
            legacy_print_catalog=None,
            display_labels_override={"vinyl": "Vinyl"},
        ):
            summary["sunnycrest_workshop_overrides"] = "applied"
        else:
            summary["sunnycrest_workshop_overrides"] = "noop_matched"
    else:
        summary["sunnycrest_workshop_overrides"] = "tenant_absent"

    # Step 4: canonical Wilbert Q1 display label override (canonical
    # "Life's Reflections" per r74 substrate). Canonical seed no-op
    # canonical-skip when canonical Wilbert tenant absent (documented
    # for canonical future Wilbert tenant onboarding).
    wilbert = db.query(Company).filter(Company.slug == "wilbert").first()
    if wilbert is not None:
        if _seed_workshop_catalog_overrides(
            db,
            wilbert,
            font_catalog=None,
            emblem_catalog=None,
            legacy_print_catalog=None,
            display_labels_override={"vinyl": _WILBERT_VINYL_DISPLAY_LABEL},
        ):
            summary["wilbert_q1_label"] = "applied"
        else:
            summary["wilbert_q1_label"] = "noop_matched"
    else:
        summary["wilbert_q1_label"] = "absent"

    # Step 5+6: canonical Generation Focus instance + canonical Document
    # substrate for FC-2026-0001. Use canonical Phase 1A
    # ``open_instance`` + ``commit_canvas_state`` service path so canonical
    # invariants canonical-hold (canonical D-9 Document + canonical
    # DocumentVersion + canonical case_merchandise denormalization fire
    # canonically).
    from app.models.generation_focus_instance import GenerationFocusInstance

    existing_instance = (
        db.query(GenerationFocusInstance)
        .filter(
            GenerationFocusInstance.company_id == hopkins.id,
            GenerationFocusInstance.linked_entity_type == "fh_case",
            GenerationFocusInstance.linked_entity_id == case.id,
            GenerationFocusInstance.template_type
            == "burial_vault_personalization_studio",
        )
        .first()
    )

    if existing_instance is None:
        from app.services.personalization_studio import instance_service

        # Resolve canonical Hopkins director for canonical opened_by /
        # committed_by attribution.
        director = (
            db.query(User)
            .filter(
                User.company_id == hopkins.id,
                User.email == "director1@hopkinsfh.test",
            )
            .first()
        )
        director_id = director.id if director else None

        ps_instance = instance_service.open_instance(
            db,
            company_id=hopkins.id,
            template_type="burial_vault_personalization_studio",
            authoring_context="funeral_home_with_family",
            linked_entity_id=case.id,
            opened_by_user_id=director_id,
        )
        instance_service.commit_canvas_state(
            db,
            instance_id=ps_instance.id,
            canvas_state=_hopkins_demo_canvas_state(case.id),
            committed_by_user_id=director_id,
        )
        # Canonical Phase 1F state: family approved + canonical
        # committed lifecycle_state.
        now = datetime.now(timezone.utc)
        ps_instance.lifecycle_state = "committed"
        ps_instance.family_approval_status = "approved"
        ps_instance.committed_at = now
        ps_instance.committed_by_user_id = director_id
        ps_instance.family_approval_decided_at = now
        # Canonical Phase 1E action_payload snapshot for canonical
        # decedent_name resolution at canonical email template var.
        ps_instance.action_payload = {
            "actions": [
                {
                    "action_type": "personalization_studio_family_approval",
                    "action_target_type": "generation_focus_instance",
                    "action_target_id": ps_instance.id,
                    "action_metadata": {
                        "decedent_name": "John Michael Smith",
                        "fh_director_name": "Michael Torres",
                        "family_email": "mary.smith@example.com",
                    },
                    "action_status": "approved",
                    "action_completed_at": now.isoformat(),
                    "action_completed_by": "mary.smith@example.com",
                    "action_completion_metadata": {
                        "outcome": "approve",
                        "auth_method": "magic_link",
                    },
                }
            ]
        }
        db.flush()
        summary["ps_document"] = "created"
        summary["ps_instance"] = "created"
    else:
        ps_instance = existing_instance
        summary["ps_document"] = "noop_matched"
        summary["ps_instance"] = "noop_matched"

    # Step 6: canonical pre-shared DocumentShare Hopkins→Sunnycrest at
    # canonical D-6 substrate. Canonical existence check first +
    # canonical idempotent re-seed.
    if sunnycrest is not None and ps_instance.document_id is not None:
        from app.models.document_share import DocumentShare
        from app.services.documents import document_sharing_service

        existing_share = (
            db.query(DocumentShare)
            .filter(
                DocumentShare.document_id == ps_instance.document_id,
                DocumentShare.target_company_id == sunnycrest.id,
                DocumentShare.revoked_at.is_(None),
            )
            .first()
        )
        if existing_share is None:
            from app.models.canonical_document import Document

            document = (
                db.query(Document)
                .filter(Document.id == ps_instance.document_id)
                .first()
            )
            if document is not None:
                # Resolve canonical FH director attribution for
                # canonical granted_by_user_id.
                director = (
                    db.query(User)
                    .filter(
                        User.company_id == hopkins.id,
                        User.email == "director1@hopkinsfh.test",
                    )
                    .first()
                )
                document_sharing_service.grant_share(
                    db,
                    document=document,
                    target_company_id=sunnycrest.id,
                    granted_by_user_id=director.id if director else None,
                    reason=(
                        "Memorial design approved by family — shared "
                        "for fulfillment"
                    ),
                    source_module=(
                        "personalization_studio.demo_seed_phase1g"
                    ),
                    enforce_relationship=True,
                )
                summary["documentshare"] = "created"
            else:
                summary["documentshare"] = "document_missing"
        else:
            summary["documentshare"] = "noop_matched"
    else:
        summary["documentshare"] = "tenant_absent_or_no_document"

    db.commit()
    return summary


# ─────────────────────────────────────────────────────────────────────
# Phase 2D — Step 2 Urn Vault Personalization Studio demo seed
# integration
#
# Per Phase 2D build prompt + substrate-consumption-follower discipline:
# parallels Phase 1G ``_seed_personalization_studio_phase1g`` structure
# verbatim with urn-specific scope (template_type=urn_vault_personalization_studio,
# document_type=urn_vault_personalization_studio, urn-specific canvas
# state shape per Phase 2A factory dispatch).
#
# Idempotent seed pattern preserved per Sessions 1-8 + Phase 1G
# precedent — fresh→create + matched→noop + differing→update.
#
# Net-new substrate at Phase 2D (per substrate-consumption-follower
# enumeration):
#   - 1 helper function (this) parallel to Phase 1G helper structure
#   - Hopkins + Sunnycrest per-tenant urn vault Workshop catalog overrides
#   - Step 2 GenerationFocusInstance for cremation case (when present)
# ─────────────────────────────────────────────────────────────────────


# Hopkins per-tenant urn vault Workshop catalog override (subset of
# canonical-default catalogs per Tune mode boundary). Mirrors Phase 1G
# Hopkins burial vault subset; urn-specific subset narrower per
# §3.26.11.12.19.6 per-template Tune mode customization scope.
_HOPKINS_URN_FONT_CATALOG = ["serif", "italic"]
_HOPKINS_URN_EMBLEM_CATALOG = [
    "rose",
    "cross",
    "praying_hands",
    "dove",
]
_HOPKINS_URN_LEGACY_PRINT_CATALOG: list[str] | None = None  # default


# Sunnycrest per-tenant urn vault Workshop catalog override. Q1 "Vinyl"
# display label override is shared at category scope per §3.26.11.12.19.6
# scope freeze (already applied at Phase 1G); Phase 2D does not re-apply.
_SUNNYCREST_URN_FONT_CATALOG = ["serif", "sans"]
_SUNNYCREST_URN_EMBLEM_CATALOG = ["rose", "cross", "dove"]


# Empty canvas state for the Step 2 cremation demo case. Mirrors Phase
# 1G ``_hopkins_demo_canvas_state`` shape with urn-specific
# ``urn_product`` slot per Phase 2A factory dispatch.
def _hopkins_step2_demo_canvas_state(case_id: str) -> dict:
    return {
        "schema_version": 1,
        "template_type": "urn_vault_personalization_studio",
        "canvas_layout": {
            "elements": [
                {
                    "id": str(uuid.uuid4()),
                    "element_type": "name_text",
                    "x": 100,
                    "y": 60,
                    "config": {
                        "name_display": "ROBERT M. HARRIS",
                        "font": "serif",
                    },
                },
                {
                    "id": str(uuid.uuid4()),
                    "element_type": "emblem",
                    "x": 100,
                    "y": 140,
                    "config": {"emblem_key": "dove"},
                },
            ],
        },
        "urn_product": {
            "urn_product_id": None,
            "urn_product_name": "Heritage Bronze Urn",
        },
        "emblem_key": "dove",
        "name_display": "ROBERT M. HARRIS",
        "font": "serif",
        "birth_date_display": "January 12, 1945",
        "death_date_display": "April 15, 2026",
        "nameplate_text": None,
        "options": {
            "legacy_print": None,
            "physical_nameplate": None,
            "physical_emblem": {},
            "vinyl": None,
        },
        "family_approval_status": "approved",
    }


def _seed_step2_cremation_case(db, hopkins_id, director_id):
    """Phase 2D Step 2 cremation demo case.

    Creates a parallel demo case to FC-2026-0001 (burial vault) — Step 2
    cremation case for Urn Vault Personalization Studio demo path.
    Idempotent via ``case_number`` lookup.

    Returns the FuneralCase row.
    """
    existing = db.query(FuneralCase).filter(
        FuneralCase.company_id == hopkins_id,
        FuneralCase.case_number == "FC-2026-0002",
    ).first()
    if existing:
        return existing

    case = case_service.create_case(db, hopkins_id, director_id=director_id)
    case.case_number = "FC-2026-0002"
    case.current_step = "story"
    case.completed_steps = [
        "arrangement_conference",
        "vital_statistics",
        "authorization",
        "service_planning",
        "obituary",
        "merchandise_urn",
    ]
    db.commit()

    # Deceased — Robert M. Harris (Step 2 cremation demo decedent)
    dec = db.query(CaseDeceased).filter(CaseDeceased.case_id == case.id).first()
    dec.first_name = "Robert"
    dec.middle_name = "Michael"
    dec.last_name = "Harris"
    dec.date_of_birth = date(1945, 1, 12)
    dec.date_of_death = date(2026, 4, 15)
    dec.sex = "male"
    dec.religion = "Methodist"
    dec.occupation = "Engineer (retired)"
    dec.marital_status = "widowed"
    dec.residence_city = "Syracuse"
    dec.residence_state = "NY"

    # Disposition — cremation
    disp = db.query(CaseDisposition).filter(CaseDisposition.case_id == case.id).first()
    disp.disposition_type = "cremation"
    disp.death_certificate_status = "pending"

    # Service — memorial service
    svc = db.query(FHCaseService).filter(FHCaseService.case_id == case.id).first()
    svc.service_type = "memorial"
    svc.service_date = date(2026, 4, 22)
    svc.service_time = time(10, 0)
    svc.service_location_name = "Hopkins Memorial Chapel"
    svc.service_location_address = "100 Hopkins Way, Syracuse, NY"

    # Informant — son (primary + authorizing)
    db.add(CaseInformant(
        id=str(uuid.uuid4()),
        case_id=case.id,
        company_id=hopkins_id,
        name="James Harris",
        relationship="son",
        phone="555-0287",
        is_primary=True,
        is_authorizing=True,
        authorization_signed_at=datetime.now(timezone.utc),
        authorization_method="in_person",
    ))

    # Merchandise — urn (Step 2 demo)
    merch = db.query(CaseMerchandise).filter(CaseMerchandise.case_id == case.id).first()
    merch.urn_name = "Heritage Bronze Urn"
    merch.urn_price = 295.00
    merch.urn_personalization_notes = (
        "Family-selected dove emblem; serif name plate; "
        "engineer occupation honored at memorial."
    )

    db.commit()
    db.refresh(case)
    return case


def _seed_personalization_studio_step2(db, hopkins, sunnycrest):
    """Phase 2D Step 2 demo seed integration.

    Substrate-consumption-follower extension parallel to Phase 1G
    ``_seed_personalization_studio_phase1g`` structure:

      1. Step 2 Intelligence prompts (Phase 2B idempotent re-execution)
      2. Hopkins per-tenant urn vault Workshop catalog overrides
      3. Sunnycrest per-tenant urn vault Workshop catalog overrides
      4. Step 2 cremation demo case FC-2026-0002 (Robert Harris)
      5. Step 2 GenerationFocusInstance for FC-2026-0002 with urn canvas
         state pre-rendered (committed lifecycle + family-approved)
      6. Pre-shared Hopkins→Sunnycrest DocumentShare for Step 2 instance

    Returns summary dict for stdout consumption.
    """
    summary: dict = {
        "step2_prompts": "skipped",
        "hopkins_urn_overrides": "skipped",
        "sunnycrest_urn_overrides": "skipped",
        "step2_case": "skipped",
        "step2_ps_document": "skipped",
        "step2_ps_instance": "skipped",
        "step2_documentshare": "skipped",
    }

    # Step 1: Phase 2B Intelligence prompts idempotent seed.
    try:
        from scripts.seed_personalization_studio_step2_intelligence import (
            seed as seed_step2_prompts,
        )

        created_p, created_v = seed_step2_prompts(db)
        if created_p > 0 or created_v > 0:
            summary["step2_prompts"] = (
                f"created prompts={created_p} versions={created_v}"
            )
        else:
            summary["step2_prompts"] = "noop_matched"
    except Exception as exc:  # noqa: BLE001 — best-effort seed
        summary["step2_prompts"] = f"failed: {type(exc).__name__}"

    # Step 2: Hopkins per-tenant urn vault Workshop overrides.
    if _seed_workshop_catalog_overrides(
        db,
        hopkins,
        font_catalog=_HOPKINS_URN_FONT_CATALOG,
        emblem_catalog=_HOPKINS_URN_EMBLEM_CATALOG,
        legacy_print_catalog=_HOPKINS_URN_LEGACY_PRINT_CATALOG,
        display_labels_override=None,
        template_type="urn_vault_personalization_studio",
    ):
        summary["hopkins_urn_overrides"] = "applied"
    else:
        summary["hopkins_urn_overrides"] = "noop_matched"

    # Step 3: Sunnycrest per-tenant urn vault Workshop overrides.
    if sunnycrest is not None:
        sunnycrest_fresh = (
            db.query(Company).filter(Company.id == sunnycrest.id).first()
        )
        if _seed_workshop_catalog_overrides(
            db,
            sunnycrest_fresh,
            font_catalog=_SUNNYCREST_URN_FONT_CATALOG,
            emblem_catalog=_SUNNYCREST_URN_EMBLEM_CATALOG,
            legacy_print_catalog=None,
            display_labels_override=None,
            template_type="urn_vault_personalization_studio",
        ):
            summary["sunnycrest_urn_overrides"] = "applied"
        else:
            summary["sunnycrest_urn_overrides"] = "noop_matched"
    else:
        summary["sunnycrest_urn_overrides"] = "tenant_absent"

    # Step 4: Step 2 cremation demo case.
    director = (
        db.query(User)
        .filter(
            User.company_id == hopkins.id,
            User.email == "director1@hopkinsfh.test",
        )
        .first()
    )
    if director is None:
        summary["step2_case"] = "director_missing"
        db.commit()
        return summary

    case_existed = (
        db.query(FuneralCase)
        .filter(
            FuneralCase.company_id == hopkins.id,
            FuneralCase.case_number == "FC-2026-0002",
        )
        .first()
        is not None
    )
    case = _seed_step2_cremation_case(db, hopkins.id, director.id)
    summary["step2_case"] = "noop_matched" if case_existed else "created"

    # Step 5: GenerationFocusInstance + Document for Step 2 case.
    from app.models.generation_focus_instance import GenerationFocusInstance

    existing_instance = (
        db.query(GenerationFocusInstance)
        .filter(
            GenerationFocusInstance.company_id == hopkins.id,
            GenerationFocusInstance.linked_entity_type == "fh_case",
            GenerationFocusInstance.linked_entity_id == case.id,
            GenerationFocusInstance.template_type
            == "urn_vault_personalization_studio",
        )
        .first()
    )

    if existing_instance is None:
        from app.services.personalization_studio import instance_service

        ps_instance = instance_service.open_instance(
            db,
            company_id=hopkins.id,
            template_type="urn_vault_personalization_studio",
            authoring_context="funeral_home_with_family",
            linked_entity_id=case.id,
            opened_by_user_id=director.id,
        )
        instance_service.commit_canvas_state(
            db,
            instance_id=ps_instance.id,
            canvas_state=_hopkins_step2_demo_canvas_state(case.id),
            committed_by_user_id=director.id,
        )
        # Step 2 family-approved committed state (mirrors Phase 1G).
        now = datetime.now(timezone.utc)
        ps_instance.lifecycle_state = "committed"
        ps_instance.family_approval_status = "approved"
        ps_instance.committed_at = now
        ps_instance.committed_by_user_id = director.id
        ps_instance.family_approval_decided_at = now
        ps_instance.action_payload = {
            "actions": [
                {
                    "action_type": "personalization_studio_family_approval",
                    "action_target_type": "generation_focus_instance",
                    "action_target_id": ps_instance.id,
                    "action_metadata": {
                        "decedent_name": "Robert Michael Harris",
                        "fh_director_name": "Michael Torres",
                        "family_email": "james.harris@example.com",
                    },
                    "action_status": "approved",
                    "action_completed_at": now.isoformat(),
                    "action_completed_by": "james.harris@example.com",
                    "action_completion_metadata": {
                        "outcome": "approve",
                        "auth_method": "magic_link",
                    },
                }
            ]
        }
        db.flush()
        summary["step2_ps_document"] = "created"
        summary["step2_ps_instance"] = "created"
    else:
        ps_instance = existing_instance
        summary["step2_ps_document"] = "noop_matched"
        summary["step2_ps_instance"] = "noop_matched"

    # Step 6: pre-shared DocumentShare Hopkins → Sunnycrest for Step 2.
    if sunnycrest is not None and ps_instance.document_id is not None:
        from app.models.document_share import DocumentShare
        from app.services.documents import document_sharing_service

        existing_share = (
            db.query(DocumentShare)
            .filter(
                DocumentShare.document_id == ps_instance.document_id,
                DocumentShare.target_company_id == sunnycrest.id,
                DocumentShare.revoked_at.is_(None),
            )
            .first()
        )
        if existing_share is None:
            from app.models.canonical_document import Document

            document = (
                db.query(Document)
                .filter(Document.id == ps_instance.document_id)
                .first()
            )
            if document is not None:
                document_sharing_service.grant_share(
                    db,
                    document=document,
                    target_company_id=sunnycrest.id,
                    granted_by_user_id=director.id,
                    reason=(
                        "Memorial urn design approved by family — "
                        "shared for fulfillment (Step 2 demo)"
                    ),
                    source_module=(
                        "personalization_studio.demo_seed_step2"
                    ),
                    enforce_relationship=True,
                )
                summary["step2_documentshare"] = "created"
            else:
                summary["step2_documentshare"] = "document_missing"
        else:
            summary["step2_documentshare"] = "noop_matched"
    else:
        summary["step2_documentshare"] = "tenant_absent_or_no_document"

    db.commit()
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Actually apply changes (default: dry-run)")
    parser.add_argument("--force", action="store_true", help="Recreate the demo case even if one exists")
    # R-1.6: --idempotent is the explicit-intent alias for the default
    # ensure-or-skip behavior (no --force). The flag is a verbose marker
    # for railway-start.sh + CI invocations: "I expect this to be safe
    # to re-run on every deploy." If --force is passed alongside
    # --idempotent, --force takes precedence (caller wanted explicit
    # recreation) and the script logs a warning.
    parser.add_argument(
        "--idempotent",
        action="store_true",
        help=(
            "Verbose-skip mode: re-run on existing data is a no-op. "
            "Same end-state as default behavior. Logs each ensure/skip "
            "decision. Safe for railway-start.sh re-invocation."
        ),
    )
    args = parser.parse_args()

    if args.force and args.idempotent:
        print(
            "WARNING: --force overrides --idempotent. The demo case will "
            "be deleted + recreated."
        )

    if os.getenv("ENVIRONMENT", "").lower() == "production":
        print("SAFETY: Refusing to run in production.")
        sys.exit(2)

    if not args.apply:
        print("DRY-RUN — pass --apply to execute.")
        print("Would create/ensure:")
        print("  - hopkins-fh tenant + admin + 2 directors + office")
        print("  - st-marys cemetery tenant + admin")
        print("  - 40 plots in 4 sections with map config")
        print("  - platform_tenant_relationships: hopkins-fh → sunnycrest (manufacturer)")
        print("  - platform_tenant_relationships: hopkins-fh → st-marys (cemetery)")
        print("  - Demo case FC-2026-0001 (John Michael Smith) at the Story step")
        print("  - Phase 1G — Personalization Studio canonical demo seed:")
        print("    · email.personalization_studio_share_granted +")
        print("      email.personalization_studio_family_approval_request templates")
        print("    · Hopkins per-tenant Workshop catalog overrides")
        print("    · Sunnycrest per-tenant Workshop catalog overrides + Q1 'Vinyl' label")
        print("    · Generation Focus instance for FC-2026-0001 (committed + family-approved)")
        print("    · pre-shared DocumentShare Hopkins → Sunnycrest")
        print("  - Phase 2D — Step 2 Urn Vault Personalization Studio demo seed:")
        print("    · 3 Phase 2B Intelligence prompts (urn_vault_personalization.*)")
        print("    · Hopkins per-tenant urn vault Workshop catalog overrides")
        print("    · Sunnycrest per-tenant urn vault Workshop catalog overrides")
        print("    · Step 2 cremation demo case FC-2026-0002 (Robert Harris)")
        print("    · Generation Focus instance for FC-2026-0002 (committed + family-approved)")
        print("    · pre-shared DocumentShare Hopkins → Sunnycrest (Step 2)")
        return

    db = SessionLocal()
    try:
        # Hopkins FH
        # R-1.6: slug aligned to canonical CLAUDE.md docs ("hopkins-fh" not "hopkinsfh").
        # Email domain stays @hopkinsfh.test (separate from tenant slug).
        hopkins = _ensure_company(db, "hopkins-fh", {
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
        # R-1.6: slug aligned to canonical CLAUDE.md docs ("st-marys" not "stmarys").
        stmarys = _ensure_company(db, "st-marys", {
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

        # Phase 1G — Personalization Studio demo seed integration.
        ps_summary = _seed_personalization_studio_phase1g(
            db, hopkins, sunnycrest, case
        )
        print(
            f"  ✓ Personalization Studio demo seed (Step 1): "
            f"templates={ps_summary['email_templates']}, "
            f"hopkins_overrides={ps_summary['hopkins_workshop_overrides']}, "
            f"sunnycrest_overrides={ps_summary['sunnycrest_workshop_overrides']}, "
            f"wilbert_q1={ps_summary['wilbert_q1_label']}, "
            f"document={ps_summary['ps_document']}, "
            f"instance={ps_summary['ps_instance']}, "
            f"share={ps_summary['documentshare']}"
        )

        # Phase 2D — Step 2 Urn Vault Personalization Studio demo seed.
        step2_summary = _seed_personalization_studio_step2(
            db, hopkins, sunnycrest
        )
        print(
            f"  ✓ Personalization Studio demo seed (Step 2 urn vault): "
            f"prompts={step2_summary['step2_prompts']}, "
            f"hopkins_urn_overrides={step2_summary['hopkins_urn_overrides']}, "
            f"sunnycrest_urn_overrides={step2_summary['sunnycrest_urn_overrides']}, "
            f"case={step2_summary['step2_case']}, "
            f"document={step2_summary['step2_ps_document']}, "
            f"instance={step2_summary['step2_ps_instance']}, "
            f"share={step2_summary['step2_documentshare']}"
        )

        print("\n✓ Demo scenario seeded.")
        print(f"  Login: admin@hopkinsfh.test / DemoAdmin123!")
        print(f"  Director: director1@hopkinsfh.test / DemoDirector123!")
        print(f"  Open {case.case_number} and click 'Continue: The Story →' to demo the Approve All flow.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
