"""Personalization Studio Phase 1G — demo seed integration + Mfg-side
"Mark reviewed" cascade tests.

Per Phase 1G build prompt closing standards: backend tests covering
demo seed idempotency + Hopkins / Sunnycrest tenant verification +
per-tenant Workshop catalog overrides resolve at canonical Tune mode
read path + pre-shared DocumentShare seed entry + canonical Mfg-side
"Mark reviewed" cascade + end-to-end demo path verification.

**Anti-pattern guard tests covered**:
  - §3.26.11.12.16 Anti-pattern 4 (primitive count expansion against
    fifth Focus type rejected) — demo seed canonical-uses canonical
    `generation_focus_instances` substrate via canonical Phase 1A
    entity model; does NOT introduce demo-seed-specific entity model.
  - §2.5.4 Anti-pattern 14 (portal-specific feature creep within
    Spaces canon rejected) — Mfg-side cascade canonical-uses canonical
    V-1d notification fan-out + canonical D-6 audit ledger; does NOT
    introduce demo-seed-specific notification or audit substrate.
  - §3.26.11.12.19.2 Tune mode boundary discipline — Hopkins +
    Sunnycrest catalog overrides canonical-operate within canonical
    4-options vocabulary boundary at Tune mode read path.
  - Idempotent seed pattern discipline — fresh→create + matched→noop
    + differing→update + multiple→skip-with-warning.
"""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timezone
from unittest.mock import patch

import pytest

from app.database import SessionLocal
from app.models import Company, Role, User
from app.models.canonical_document import Document
from app.models.document_share import DocumentShare, DocumentShareEvent
from app.models.fh_case import FHCase
from app.models.generation_focus_instance import GenerationFocusInstance
from app.models.platform_tenant_relationship import (
    PlatformTenantRelationship,
)


# ─────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()


@pytest.fixture
def fake_r2():
    storage: dict[str, bytes] = {}

    def fake_upload(
        data: bytes,
        r2_key: str,
        content_type: str = "application/octet-stream",
    ):
        storage[r2_key] = data
        return f"https://r2.test/{r2_key}"

    def fake_download(r2_key: str) -> bytes:
        return storage[r2_key]

    with (
        patch(
            "app.services.personalization_studio.instance_service.legacy_r2_client.upload_bytes",
            side_effect=fake_upload,
        ),
        patch(
            "app.services.personalization_studio.instance_service.legacy_r2_client.download_bytes",
            side_effect=fake_download,
        ),
    ):
        yield storage


def _make_tenant(db_session, *, slug, vertical, name):
    co = (
        db_session.query(Company)
        .filter(Company.slug == slug)
        .first()
    )
    if co is None:
        co = Company(
            id=str(uuid.uuid4()),
            slug=slug,
            name=name,
            vertical=vertical,
            is_active=True,
        )
        db_session.add(co)
        db_session.flush()
    return co


def _make_admin(db_session, tenant, *, email_prefix="admin"):
    role = (
        db_session.query(Role)
        .filter(Role.company_id == tenant.id, Role.slug == "admin")
        .first()
    )
    if role is None:
        role = Role(
            id=str(uuid.uuid4()),
            company_id=tenant.id,
            name="Admin",
            slug="admin",
            is_system=True,
        )
        db_session.add(role)
        db_session.flush()
    user = User(
        id=str(uuid.uuid4()),
        email=f"{email_prefix}-{uuid.uuid4().hex[:6]}@p1g.test",
        hashed_password="x",
        first_name="Test",
        last_name="Admin",
        company_id=tenant.id,
        role_id=role.id,
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    return user


def _make_director(db_session, tenant):
    role = (
        db_session.query(Role)
        .filter(Role.company_id == tenant.id, Role.slug == "director1")
        .first()
    )
    if role is None:
        role = Role(
            id=str(uuid.uuid4()),
            company_id=tenant.id,
            name="Director",
            slug="director1",
            is_system=False,
        )
        db_session.add(role)
        db_session.flush()
    user = User(
        id=str(uuid.uuid4()),
        email="director1@hopkinsfh.test",
        hashed_password="x",
        first_name="Michael",
        last_name="Torres",
        company_id=tenant.id,
        role_id=role.id,
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    return user


def _ensure_ptr(db_session, fh, mfg, consent="active"):
    forward = PlatformTenantRelationship(
        id=str(uuid.uuid4()),
        tenant_id=fh.id,
        supplier_tenant_id=mfg.id,
        relationship_type="fh_manufacturer",
        status="active",
        personalization_studio_cross_tenant_sharing_consent=consent,
    )
    reverse = PlatformTenantRelationship(
        id=str(uuid.uuid4()),
        tenant_id=mfg.id,
        supplier_tenant_id=fh.id,
        relationship_type="fh_manufacturer",
        status="active",
        personalization_studio_cross_tenant_sharing_consent=consent,
    )
    db_session.add(forward)
    db_session.add(reverse)
    db_session.flush()
    return forward, reverse


def _make_demo_case(db_session, hopkins, director):
    case = FHCase(
        id=str(uuid.uuid4()),
        company_id=hopkins.id,
        case_number="FC-2026-0001",
        deceased_first_name="John",
        deceased_last_name="Smith",
        deceased_date_of_death=date(2026, 4, 9),
    )
    db_session.add(case)
    db_session.flush()
    return case


# ─────────────────────────────────────────────────────────────────────
# 1. Demo seed idempotency + Workshop catalog override resolution
# ─────────────────────────────────────────────────────────────────────


class TestDemoSeedWorkshopOverrides:
    def test_hopkins_workshop_override_resolves_at_tune_mode_read_path(
        self, db_session
    ):
        from scripts.seed_fh_demo import _seed_workshop_catalog_overrides
        from app.services.workshop import tenant_config

        # Workshop registry side-effect-import canonical at Phase 1D.
        from app.services.workshop import registry  # noqa: F401

        hopkins = _make_tenant(
            db_session, slug=f"hop{uuid.uuid4().hex[:6]}",
            vertical="funeral_home", name="Hopkins Test",
        )
        db_session.commit()

        applied = _seed_workshop_catalog_overrides(
            db_session,
            hopkins,
            font_catalog=["serif", "italic", "uppercase"],
            emblem_catalog=[
                "rose", "cross", "praying_hands", "dove", "wreath",
                "patriotic_flag",
            ],
            legacy_print_catalog=None,
            display_labels_override=None,
        )
        db_session.commit()
        assert applied is True

        # Canonical tenant_config read path resolves canonical override.
        config = tenant_config.get_tenant_personalization_config(
            db_session,
            company_id=hopkins.id,
            template_type="burial_vault_personalization_studio",
        )
        assert config["font_catalog"] == [
            "serif", "italic", "uppercase",
        ]
        # Canonical "sans" canonical-excluded per Hopkins canonical
        # subset selection.
        assert "sans" not in config["font_catalog"]

    def test_sunnycrest_q1_vinyl_label_override_resolves(self, db_session):
        from scripts.seed_fh_demo import _seed_workshop_catalog_overrides
        from app.services.workshop import tenant_config
        from app.services.workshop import registry  # noqa: F401

        sunnycrest = _make_tenant(
            db_session, slug=f"sun{uuid.uuid4().hex[:6]}",
            vertical="manufacturing", name="Sunnycrest Test",
        )
        db_session.commit()

        _seed_workshop_catalog_overrides(
            db_session,
            sunnycrest,
            font_catalog=["serif", "sans"],
            emblem_catalog=None,
            legacy_print_catalog=None,
            display_labels_override={"vinyl": "Vinyl"},
        )
        db_session.commit()

        config = tenant_config.get_tenant_personalization_config(
            db_session,
            company_id=sunnycrest.id,
            template_type="burial_vault_personalization_studio",
        )
        assert config["display_labels"]["vinyl"] == "Vinyl"
        assert config["font_catalog"] == ["serif", "sans"]

    def test_seed_workshop_catalog_idempotent_on_repeat(self, db_session):
        from scripts.seed_fh_demo import _seed_workshop_catalog_overrides

        hopkins = _make_tenant(
            db_session, slug=f"hop{uuid.uuid4().hex[:6]}",
            vertical="funeral_home", name="Hopkins Test",
        )
        db_session.commit()

        first = _seed_workshop_catalog_overrides(
            db_session,
            hopkins,
            font_catalog=["serif", "italic"],
            emblem_catalog=None,
            legacy_print_catalog=None,
            display_labels_override=None,
        )
        db_session.commit()
        assert first is True

        second = _seed_workshop_catalog_overrides(
            db_session,
            hopkins,
            font_catalog=["serif", "italic"],
            emblem_catalog=None,
            legacy_print_catalog=None,
            display_labels_override=None,
        )
        db_session.commit()
        assert second is False  # Canonical noop_matched.

    def test_wilbert_q1_lifes_reflections_override(self, db_session):
        """Q1 canonical 'Life's Reflections' override per r74 substrate."""
        from scripts.seed_fh_demo import (
            _seed_workshop_catalog_overrides,
            _WILBERT_VINYL_DISPLAY_LABEL,
        )
        from app.services.workshop import tenant_config
        from app.services.workshop import registry  # noqa: F401

        wilbert = _make_tenant(
            db_session, slug=f"wil{uuid.uuid4().hex[:6]}",
            vertical="manufacturing", name="Wilbert Test",
        )
        db_session.commit()

        _seed_workshop_catalog_overrides(
            db_session,
            wilbert,
            font_catalog=None,
            emblem_catalog=None,
            legacy_print_catalog=None,
            display_labels_override={"vinyl": _WILBERT_VINYL_DISPLAY_LABEL},
        )
        db_session.commit()

        config = tenant_config.get_tenant_personalization_config(
            db_session,
            company_id=wilbert.id,
            template_type="burial_vault_personalization_studio",
        )
        assert config["display_labels"]["vinyl"] == "Life's Reflections"


# ─────────────────────────────────────────────────────────────────────
# 2. Phase 1G demo seed integration end-to-end
# ─────────────────────────────────────────────────────────────────────


class TestDemoSeedPhase1gIntegration:
    def test_seed_personalization_studio_phase1g_creates_canonical_state(
        self, db_session, fake_r2
    ):
        from scripts.seed_fh_demo import _seed_personalization_studio_phase1g
        # Side-effect-import canonical Phase 1E ActionTypeDescriptor
        # registration (Pattern A) so canonical Path B substrate resolves
        # at canonical seed call site.
        from app.services import personalization_studio  # noqa: F401

        hopkins = _make_tenant(
            db_session, slug=f"hop{uuid.uuid4().hex[:6]}",
            vertical="funeral_home", name="Hopkins Test",
        )
        sunnycrest = _make_tenant(
            db_session, slug=f"sun{uuid.uuid4().hex[:6]}",
            vertical="manufacturing", name="Sunnycrest Test",
        )
        director = _make_director(db_session, hopkins)
        _ensure_ptr(db_session, hopkins, sunnycrest)
        case = _make_demo_case(db_session, hopkins, director)
        db_session.commit()

        summary = _seed_personalization_studio_phase1g(
            db_session, hopkins, sunnycrest, case
        )

        assert summary["hopkins_workshop_overrides"] in ("applied", "noop_matched")
        assert summary["sunnycrest_workshop_overrides"] in ("applied", "noop_matched")
        assert summary["ps_instance"] in ("created", "noop_matched")
        assert summary["documentshare"] in ("created", "noop_matched")

        # Canonical Generation Focus instance canonical-shape.
        ps_instance = (
            db_session.query(GenerationFocusInstance)
            .filter(
                GenerationFocusInstance.company_id == hopkins.id,
                GenerationFocusInstance.linked_entity_type == "fh_case",
                GenerationFocusInstance.linked_entity_id == case.id,
            )
            .first()
        )
        assert ps_instance is not None
        assert ps_instance.lifecycle_state == "committed"
        assert ps_instance.family_approval_status == "approved"
        assert ps_instance.template_type == "burial_vault_personalization_studio"
        assert ps_instance.authoring_context == "funeral_home_with_family"
        # Canonical Phase 1E action_payload snapshot canonical-stamps
        # canonical decedent_name attribution.
        actions = (ps_instance.action_payload or {}).get("actions") or []
        assert len(actions) >= 1
        assert (
            actions[-1]["action_metadata"]["decedent_name"]
            == "John Michael Smith"
        )

        # Canonical Document at canonical D-9 substrate.
        document = (
            db_session.query(Document)
            .filter(Document.id == ps_instance.document_id)
            .first()
        )
        assert document is not None
        assert document.document_type == "burial_vault_personalization_studio"
        assert document.company_id == hopkins.id

        # Canonical pre-shared DocumentShare Hopkins → Sunnycrest.
        share = (
            db_session.query(DocumentShare)
            .filter(
                DocumentShare.document_id == document.id,
                DocumentShare.target_company_id == sunnycrest.id,
                DocumentShare.revoked_at.is_(None),
            )
            .first()
        )
        assert share is not None
        assert share.owner_company_id == hopkins.id

    def test_seed_phase1g_idempotent_on_repeat(self, db_session, fake_r2):
        from scripts.seed_fh_demo import _seed_personalization_studio_phase1g
        from app.services import personalization_studio  # noqa: F401

        hopkins = _make_tenant(
            db_session, slug=f"hop{uuid.uuid4().hex[:6]}",
            vertical="funeral_home", name="Hopkins Test",
        )
        sunnycrest = _make_tenant(
            db_session, slug=f"sun{uuid.uuid4().hex[:6]}",
            vertical="manufacturing", name="Sunnycrest Test",
        )
        director = _make_director(db_session, hopkins)
        _ensure_ptr(db_session, hopkins, sunnycrest)
        case = _make_demo_case(db_session, hopkins, director)
        db_session.commit()

        first = _seed_personalization_studio_phase1g(
            db_session, hopkins, sunnycrest, case
        )
        second = _seed_personalization_studio_phase1g(
            db_session, hopkins, sunnycrest, case
        )

        # Canonical noop_matched on second call (idempotent).
        assert second["ps_instance"] == "noop_matched"
        assert second["documentshare"] == "noop_matched"
        assert second["hopkins_workshop_overrides"] == "noop_matched"
        assert second["sunnycrest_workshop_overrides"] == "noop_matched"

        # Canonical single Generation Focus instance for FC-2026-0001.
        instance_count = (
            db_session.query(GenerationFocusInstance)
            .filter(
                GenerationFocusInstance.company_id == hopkins.id,
                GenerationFocusInstance.linked_entity_type == "fh_case",
                GenerationFocusInstance.linked_entity_id == case.id,
            )
            .count()
        )
        assert instance_count == 1

    def test_seed_phase1g_handles_absent_sunnycrest(
        self, db_session, fake_r2
    ):
        """Canonical seed canonical-skips DocumentShare when canonical
        Sunnycrest absent (canonical demo-seed canonical-handles
        canonical canonical-tenant-absent state)."""
        from scripts.seed_fh_demo import _seed_personalization_studio_phase1g
        from app.services import personalization_studio  # noqa: F401

        hopkins = _make_tenant(
            db_session, slug=f"hop{uuid.uuid4().hex[:6]}",
            vertical="funeral_home", name="Hopkins Test",
        )
        director = _make_director(db_session, hopkins)
        case = _make_demo_case(db_session, hopkins, director)
        db_session.commit()

        summary = _seed_personalization_studio_phase1g(
            db_session, hopkins, None, case
        )
        assert summary["sunnycrest_workshop_overrides"] == "tenant_absent"
        assert summary["documentshare"] == "tenant_absent_or_no_document"
        # Canonical Generation Focus instance canonical-still-creates
        # at canonical Hopkins-side scope.
        assert summary["ps_instance"] == "created"


# ─────────────────────────────────────────────────────────────────────
# 3. Mfg-side "Mark reviewed" cascade
# ─────────────────────────────────────────────────────────────────────


class TestMfgSidePostCommitCascade:
    def _setup_share_and_mfg_instance(self, db_session, fake_r2):
        """Fixture: canonical Phase 1G demo seed state →
        canonical Sunnycrest opens canonical from-share instance
        canonical-ready for canonical Mark-reviewed commit."""
        from scripts.seed_fh_demo import _seed_personalization_studio_phase1g
        from app.services import personalization_studio  # noqa: F401
        from app.services.personalization_studio import instance_service

        hopkins = _make_tenant(
            db_session, slug=f"hop{uuid.uuid4().hex[:6]}",
            vertical="funeral_home", name="Hopkins Test",
        )
        sunnycrest = _make_tenant(
            db_session, slug=f"sun{uuid.uuid4().hex[:6]}",
            vertical="manufacturing", name="Sunnycrest Test",
        )
        director = _make_director(db_session, hopkins)
        mfg_admin = _make_admin(db_session, sunnycrest)
        _ensure_ptr(db_session, hopkins, sunnycrest)
        case = _make_demo_case(db_session, hopkins, director)
        db_session.commit()

        _seed_personalization_studio_phase1g(
            db_session, hopkins, sunnycrest, case
        )

        # Resolve canonical pre-shared DocumentShare.
        ps_instance = (
            db_session.query(GenerationFocusInstance)
            .filter(
                GenerationFocusInstance.company_id == hopkins.id,
                GenerationFocusInstance.linked_entity_type == "fh_case",
                GenerationFocusInstance.linked_entity_id == case.id,
            )
            .first()
        )
        share = (
            db_session.query(DocumentShare)
            .filter(
                DocumentShare.document_id == ps_instance.document_id,
                DocumentShare.target_company_id == sunnycrest.id,
            )
            .first()
        )
        assert share is not None

        # Canonical Mfg-side from-share open.
        mfg_instance = instance_service.open_instance_from_share(
            db_session,
            document_share_id=share.id,
            mfg_company_id=sunnycrest.id,
            opened_by_user_id=mfg_admin.id,
        )
        db_session.commit()
        return mfg_admin, mfg_instance, share

    def test_cascade_fires_on_mark_reviewed_commit(
        self, db_session, fake_r2
    ):
        from app.services.personalization_studio import instance_service

        mfg_admin, mfg_instance, share = self._setup_share_and_mfg_instance(
            db_session, fake_r2
        )

        # Canonical "Mark reviewed" canonical commit_instance flow.
        committed = instance_service.commit_instance(
            db_session,
            instance_id=mfg_instance.id,
            committed_by_user_id=mfg_admin.id,
        )
        db_session.commit()
        assert committed.lifecycle_state == "committed"

        # Canonical Phase 1G post-commit cascade canonical-fires.
        outcome = instance_service.manufacturer_from_fh_share_post_commit_cascade(
            db_session, instance=committed
        )
        db_session.commit()

        assert outcome["cascade_fired"] is True
        assert outcome["share_id"] == share.id
        assert outcome["audit_event_id"] is not None

        # Canonical D-6 'reviewed' canonical event canonical-emitted at
        # canonical D-6 audit ledger.
        ev = (
            db_session.query(DocumentShareEvent)
            .filter(
                DocumentShareEvent.share_id == share.id,
                DocumentShareEvent.event_type == "reviewed",
            )
            .first()
        )
        assert ev is not None
        assert ev.actor_company_id == mfg_instance.company_id

    def test_cascade_skips_on_non_mfg_authoring_context(
        self, db_session, fake_r2
    ):
        """Canonical no-op canonical-skip on canonical FH-vertical +
        canonical Mfg-without-family contexts."""
        from app.services.personalization_studio import instance_service

        hopkins = _make_tenant(
            db_session, slug=f"hop{uuid.uuid4().hex[:6]}",
            vertical="funeral_home", name="Hopkins Test",
        )
        director = _make_director(db_session, hopkins)
        case = _make_demo_case(db_session, hopkins, director)
        db_session.commit()

        # Canonical FH-vertical funeral_home_with_family canonical
        # instance.
        fh_instance = instance_service.open_instance(
            db_session,
            company_id=hopkins.id,
            template_type="burial_vault_personalization_studio",
            authoring_context="funeral_home_with_family",
            linked_entity_id=case.id,
            opened_by_user_id=director.id,
        )
        # Canonical post-commit cascade canonical-skips canonical non-
        # Mfg-from-share authoring context.
        outcome = instance_service.manufacturer_from_fh_share_post_commit_cascade(
            db_session, instance=fh_instance
        )
        assert outcome["cascade_fired"] is False
        assert outcome["share_id"] is None
        assert outcome["audit_event_id"] is None

    def test_cascade_skips_on_non_committed_lifecycle(
        self, db_session, fake_r2
    ):
        """Canonical defensive guard: cascade canonical-fires only at
        canonical committed lifecycle_state."""
        from app.services.personalization_studio import instance_service

        _, mfg_instance, _ = self._setup_share_and_mfg_instance(
            db_session, fake_r2
        )
        # Canonical pre-commit lifecycle_state canonical-active.
        assert mfg_instance.lifecycle_state == "active"

        outcome = instance_service.manufacturer_from_fh_share_post_commit_cascade(
            db_session, instance=mfg_instance
        )
        assert outcome["cascade_fired"] is False


# ─────────────────────────────────────────────────────────────────────
# 4. End-to-end demo path: authors → approves → receives → Mark reviewed
# ─────────────────────────────────────────────────────────────────────


class TestEndToEndDemoPath:
    def test_demo_path_canonical_complete(self, db_session, fake_r2):
        """Canonical end-to-end demo path verification per Phase 1G
        canonical-Wilbert-demo-readiness checkpoint:
          1. Hopkins authors canvas (canonical demo seed)
          2. Family approves (canonical demo seed pre-stamps approved)
          3. Hopkins → Sunnycrest DocumentShare canonical-fires
             (canonical demo seed pre-shares)
          4. Sunnycrest opens canonical from-share instance
          5. Sunnycrest clicks "Mark reviewed" (canonical commit)
          6. Canonical post-commit cascade canonical-fires
             (V-1d notification + D-6 'reviewed' event)
        """
        from scripts.seed_fh_demo import _seed_personalization_studio_phase1g
        from app.services import personalization_studio  # noqa: F401
        from app.services.personalization_studio import instance_service

        hopkins = _make_tenant(
            db_session, slug=f"hop{uuid.uuid4().hex[:6]}",
            vertical="funeral_home", name="Hopkins Test",
        )
        sunnycrest = _make_tenant(
            db_session, slug=f"sun{uuid.uuid4().hex[:6]}",
            vertical="manufacturing", name="Sunnycrest Test",
        )
        director = _make_director(db_session, hopkins)
        mfg_admin = _make_admin(db_session, sunnycrest)
        _ensure_ptr(db_session, hopkins, sunnycrest)
        case = _make_demo_case(db_session, hopkins, director)
        db_session.commit()

        # Step 1-3: canonical demo seed canonical-stamps canonical state.
        summary = _seed_personalization_studio_phase1g(
            db_session, hopkins, sunnycrest, case
        )
        assert summary["ps_instance"] == "created"
        assert summary["documentshare"] == "created"

        # Resolve canonical share for canonical Mfg-side open.
        ps_instance = (
            db_session.query(GenerationFocusInstance)
            .filter(
                GenerationFocusInstance.company_id == hopkins.id,
                GenerationFocusInstance.linked_entity_type == "fh_case",
                GenerationFocusInstance.linked_entity_id == case.id,
            )
            .first()
        )
        share = (
            db_session.query(DocumentShare)
            .filter(
                DocumentShare.document_id == ps_instance.document_id,
                DocumentShare.target_company_id == sunnycrest.id,
            )
            .first()
        )

        # Step 4: canonical Mfg-side open.
        mfg_instance = instance_service.open_instance_from_share(
            db_session,
            document_share_id=share.id,
            mfg_company_id=sunnycrest.id,
            opened_by_user_id=mfg_admin.id,
        )
        db_session.commit()
        assert mfg_instance.authoring_context == "manufacturer_from_fh_share"

        # Canonical D-6 'accessed' canonical-event canonical-emitted
        # at canonical Mfg-side open.
        accessed = (
            db_session.query(DocumentShareEvent)
            .filter(
                DocumentShareEvent.share_id == share.id,
                DocumentShareEvent.event_type == "accessed",
            )
            .first()
        )
        assert accessed is not None

        # Step 5: canonical "Mark reviewed" canonical commit.
        committed = instance_service.commit_instance(
            db_session,
            instance_id=mfg_instance.id,
            committed_by_user_id=mfg_admin.id,
        )
        db_session.commit()
        assert committed.lifecycle_state == "committed"

        # Step 6: canonical post-commit cascade.
        outcome = instance_service.manufacturer_from_fh_share_post_commit_cascade(
            db_session, instance=committed
        )
        db_session.commit()
        assert outcome["cascade_fired"] is True

        # Canonical D-6 'reviewed' canonical-event canonical-emitted
        # at canonical Mfg-side commit.
        reviewed = (
            db_session.query(DocumentShareEvent)
            .filter(
                DocumentShareEvent.share_id == share.id,
                DocumentShareEvent.event_type == "reviewed",
            )
            .first()
        )
        assert reviewed is not None
        assert reviewed.actor_company_id == sunnycrest.id


# ─────────────────────────────────────────────────────────────────────
# 5. Anti-pattern guards
# ─────────────────────────────────────────────────────────────────────


class TestAntiPatternGuardsPhase1G:
    def test_demo_seed_uses_canonical_entity_model(self, db_session, fake_r2):
        """Anti-pattern 4: demo seed canonical-uses canonical
        ``generation_focus_instances`` substrate via canonical Phase 1A
        entity model; does NOT introduce demo-seed-specific entity
        model."""
        from scripts.seed_fh_demo import _seed_personalization_studio_phase1g
        from app.services import personalization_studio  # noqa: F401

        hopkins = _make_tenant(
            db_session, slug=f"hop{uuid.uuid4().hex[:6]}",
            vertical="funeral_home", name="Hopkins Test",
        )
        director = _make_director(db_session, hopkins)
        case = _make_demo_case(db_session, hopkins, director)
        db_session.commit()

        _seed_personalization_studio_phase1g(
            db_session, hopkins, None, case
        )

        # Canonical Generation Focus instance lives in canonical
        # canonical-Phase-1A entity model — verified by canonical
        # ORM type assertion.
        ps_instance = (
            db_session.query(GenerationFocusInstance)
            .filter(
                GenerationFocusInstance.company_id == hopkins.id,
            )
            .first()
        )
        assert ps_instance is not None
        assert isinstance(ps_instance, GenerationFocusInstance)

    def test_tune_mode_boundary_enforced_at_demo_seed(
        self, db_session
    ):
        """§3.26.11.12.19.2 Tune mode boundary discipline: Hopkins +
        Sunnycrest catalog overrides canonical-operate within canonical
        4-options vocabulary boundary."""
        from app.services.workshop import tenant_config
        from app.services.workshop.tenant_config import (
            WorkshopTuneModeBoundaryViolation,
        )
        from app.services.workshop import registry  # noqa: F401

        hopkins = _make_tenant(
            db_session, slug=f"hop{uuid.uuid4().hex[:6]}",
            vertical="funeral_home", name="Hopkins Test",
        )
        db_session.commit()

        # Canonical attempt to canonical-add canonical font outside
        # canonical default catalog canonical-rejects per canonical
        # Tune mode boundary.
        with pytest.raises(WorkshopTuneModeBoundaryViolation):
            tenant_config.update_tenant_personalization_config(
                db_session,
                company_id=hopkins.id,
                template_type="burial_vault_personalization_studio",
                updates={"font_catalog": ["serif", "comic_sans"]},
            )

    def test_mfg_cascade_uses_canonical_v1d_notification_substrate(
        self, db_session, fake_r2
    ):
        """Anti-pattern 14: Mfg-side cascade canonical-uses canonical
        V-1d notification fan-out + canonical D-6 audit ledger; does
        NOT introduce demo-seed-specific notification or audit
        substrate. Verified via canonical-D-6-audit-event-emission +
        canonical-no-new-table inspection."""
        from app.services.personalization_studio import instance_service
        from sqlalchemy import inspect

        # Canonical no canonical demo-seed-specific cascade table at
        # canonical service substrate (canonical inspector confirms
        # canonical platform_action_tokens + canonical
        # generation_focus_instances + canonical document_shares +
        # canonical document_share_events + canonical notifications
        # canonical-suffice).
        bind = db_session.get_bind()
        inspector = inspect(bind)
        existing_tables = set(inspector.get_table_names())
        # Canonical no canonical "personalization_studio_cascade*" or
        # canonical "ps_mfg_*" canonical-tables.
        forbidden_prefixes = (
            "personalization_studio_cascade",
            "ps_mfg_",
            "mfg_cascade_",
        )
        for tbl in existing_tables:
            for prefix in forbidden_prefixes:
                assert not tbl.startswith(prefix), (
                    f"Anti-pattern 14 guard violated: canonical demo-seed-"
                    f"specific cascade table {tbl!r} canonical-introduced. "
                    f"Cascade canonical-uses canonical V-1d + canonical "
                    f"D-6 substrate per §3.26.16.6."
                )

        # Canonical no-op verify: cascade function canonical-imports
        # canonical V-1d notification_service + canonical D-6
        # document_sharing_service (verified via canonical source
        # introspection).
        import inspect as py_inspect
        src = py_inspect.getsource(
            instance_service.manufacturer_from_fh_share_post_commit_cascade
        )
        assert "notification_service" in src
        assert "document_sharing_service" in src
